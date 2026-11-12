# -*- coding: utf-8 -*-
"""Inline Job graphics tests (scene graph only, no GUI window).

Run via FreeCADCmd.exe tests/test_machine_gui.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import pivy.coin as coin
import InitMachine
import MachineGui


class TestMachineGraphics(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("MachineGui")
        self.job = self.doc.addObject("App::DocumentObjectGroupPython", "Job")
        InitMachine.Machine(self.job, self.job.Name)
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def make_provider(self):
        provider = MachineGui.MachineVP.__new__(MachineGui.MachineVP)
        provider.ViewObject = None
        provider.Object = self.job
        provider.node = coin.SoSeparator()
        provider.draw()
        return provider

    def test_draws_volume_block_planes_origin_and_axis(self):
        provider = self.make_provider()
        self.assertEqual(provider.node.getNumChildren(), 5)

    def test_config_change_redraws_without_helper_objects(self):
        provider = self.make_provider()
        self.job.FieldWidth = 900.0
        provider.updateData(self.job, "FieldWidth")
        self.assertEqual(provider.node.getNumChildren(), 5)
        for name in ("Config", "Origin", "CNCVolume", "WPL", "WPR", "Block", "RotationAxis"):
            self.assertIsNone(self.doc.getObject(name))

    def test_view_visibility_controls(self):
        provider = self.make_provider()

        class ViewOptions:
            ShowCNCVolume = True
            ShowFoamBlock = True
            ShowWorkingPlanes = True
            ShowOrigin = False
            ShowRotationAxis = True
            Visibility = True

        provider.ViewObject = ViewOptions()
        provider.draw()
        self.assertEqual(provider.node.getNumChildren(), 4)

        provider.ViewObject.ShowOrigin = True
        provider.ViewObject.ShowRotationAxis = False
        provider.draw()
        self.assertEqual(provider.node.getNumChildren(), 4)

        provider.ViewObject.ShowRotationAxis = True
        provider.ViewObject.Visibility = False
        provider.draw()
        self.assertEqual(provider.node.getNumChildren(), 0)

        provider.ViewObject.Visibility = True
        provider.draw()
        self.assertEqual(provider.node.getNumChildren(), 5)

    def test_view_properties_are_created(self):
        class ViewObject:
            def addProperty(self, prop_type, name, group, description):
                setattr(self, name, False)

        view_object = ViewObject()
        MachineGui._ensure_view_properties(view_object)
        for name in MachineGui.VIEW_PROPERTY_NAMES:
            self.assertTrue(getattr(view_object, name))

    def test_old_job_without_config_is_not_drawn(self):
        old_job = self.doc.addObject("App::DocumentObjectGroupPython", "OldJob")
        old_job.addProperty("App::PropertyString", "Type", "", "")
        old_job.Type = "Job"

        provider = self.make_provider()
        provider.Object = old_job
        provider.draw()
        self.assertEqual(provider.node.getNumChildren(), 0)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
