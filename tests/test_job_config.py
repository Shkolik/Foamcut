# -*- coding: utf-8 -*-
"""Job-owned configuration and working-plane value tests.

Run via FreeCADCmd.exe tests/test_job_config.py
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

import Part
import InitMachine
import utilities


class TestJobConfig(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("JobConfig")
        self.job = self.doc.addObject("App::DocumentObjectGroupPython", "Job")
        InitMachine.Machine(self.job, self.job.Name)
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_job_owns_configuration(self):
        self.assertTrue(hasattr(self.job, "FieldWidth"))
        self.assertTrue(hasattr(self.job, "HorizontalTravel"))
        self.assertTrue(hasattr(self.job, "PauseDuration"))
        self.assertEqual(self.job.ConfigName, "")
        self.assertIsNone(self.doc.getObject("Config"))
        for name in ("Origin", "CNCVolume", "WPL", "WPR", "Block", "RotationAxis"):
            self.assertIsNone(self.doc.getObject(name))

    def test_hidden_expression_updates_from_job(self):
        child = self.job.newObject("App::FeaturePython", "Child")
        child.addProperty("App::PropertyLength", "Value", "", "")
        utilities.bindJob(child, self.job)
        child.setExpression(".Value", utilities.jobExpression(self.job, "FieldWidth"))

        self.job.FieldWidth = 900.0
        self.doc.recompute()
        self.assertAlmostEqual(float(child.Value), 900.0, places=5)

    def test_working_planes_are_fresh_snapshots(self):
        first = utilities.getWorkingPlanes(self.job, self.doc)
        self.job.FieldWidth = 1000.0
        second = utilities.getWorkingPlanes(self.job, self.doc)

        self.assertIsNot(first[0], second[0])
        self.assertAlmostEqual(float(first[0].Position.x), -370.0, places=5)
        self.assertAlmostEqual(float(second[0].Position.x), -500.0, places=5)
        self.assertAlmostEqual(float(second[1].Position.x), 500.0, places=5)

    def test_analytic_intersection_matches_part_surface(self):
        plane = utilities.getWorkingPlanes(self.job, self.doc)[0]
        v0 = App.Vector(-300.0, -25.0, 10.0)
        v1 = App.Vector(300.0, 125.0, 80.0)

        analytic = plane.intersectLine(v0, v1)
        surface_point = plane.Shape.Surface.intersect(Part.makeLine(v0, v1).Curve)[0][0]

        self.assertAlmostEqual(analytic.x, surface_point.X, places=5)
        self.assertAlmostEqual(analytic.y, surface_point.Y, places=5)
        self.assertAlmostEqual(analytic.z, surface_point.Z, places=5)

    def test_working_planes_are_none_before_migration(self):
        old_job = self.doc.addObject("App::DocumentObjectGroupPython", "OldJob")
        old_job.addProperty("App::PropertyString", "Type", "", "")
        old_job.Type = "Job"
        self.assertIsNone(utilities.getWorkingPlanes(old_job, self.doc))


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
