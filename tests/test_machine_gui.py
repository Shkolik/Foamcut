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
import utilities


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


class TestJobSelectionPolicy(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("MachineSelection")
        self.job = self.doc.addObject("App::DocumentObjectGroupPython", "Job")
        InitMachine.Machine(self.job, self.job.Name)
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def make_view_object(self):
        class ViewObject:
            def __init__(self, obj):
                self.Object = obj
                self.RootNode = coin.SoSeparator()
                self.Visibility = True
                self.SelectionStyle = "Shape"
                self.properties = []

            def addProperty(self, prop_type, name, group, description):
                self.properties.append(name)
                setattr(self, name, False)

        return ViewObject(self.job)

    def make_provider(self, view_object):
        provider = MachineGui.MachineVP.__new__(MachineGui.MachineVP)
        provider.ViewObject = view_object
        provider.Object = self.job
        provider.node = coin.SoSeparator()
        return provider

    def test_attach_applies_the_selection_policy(self):
        view_object = self.make_view_object()
        provider = MachineGui.MachineVP(view_object)

        # - The pick style helper uses a Coin search action that is not usable
        #   on a detached scene graph in FreeCADCmd; the policy is what matters.
        original = utilities.setPickStyle
        utilities.setPickStyle = lambda view_object, style: None
        try:
            provider.attach(view_object)
        finally:
            utilities.setPickStyle = original

        self.assertEqual(view_object.SelectionStyle, "BoundBox")

    def test_finish_restoring_reapplies_the_selection_policy(self):
        view_object = self.make_view_object()
        provider = self.make_provider(view_object)

        view_object.SelectionStyle = "Shape"
        provider.finishRestoring()
        self.assertEqual(view_object.SelectionStyle, "BoundBox")

    def test_view_object_without_selection_style_is_ignored(self):
        class BareViewObject:
            pass

        provider = self.make_provider(BareViewObject())
        provider.finishRestoring()  # must not raise


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
