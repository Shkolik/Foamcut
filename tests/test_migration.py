# -*- coding: utf-8 -*-
"""Old-document migration tests.

Run via FreeCADCmd.exe tests/test_migration.py
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

import Migration
import utilities


def make_old_document():
    doc = App.newDocument("OldMigration")
    job = doc.addObject("App::DocumentObjectGroupPython", "Job")
    job.addProperty("App::PropertyString", "Type", "", "")
    job.Type = "Job"
    for name in ("ConfigName", "WPLName", "WPRName"):
        job.addProperty("App::PropertyString", name, "", "")

    config = job.newObject("App::FeaturePython", "Config")
    config.addProperty("App::PropertyString", "Type", "", "")
    config.Type = "Helper"
    for prop_type, name, value in [
        ("App::PropertyLength", "FieldWidth", 740.0),
        ("App::PropertyLength", "HorizontalTravel", 870.0),
        ("App::PropertyLength", "VerticalTravel", 330.0),
        ("App::PropertyDistance", "OriginX", 0.0),
        ("App::PropertyLength", "DiscretizationStep", 0.5),
        ("App::PropertyTime", "PauseDuration", 1.0),
        ("App::PropertySpeed", "FeedRateCut", 2.66),
        ("App::PropertyInteger", "WireMinPower", 860),
        ("App::PropertyBool", "WireStretchVerification", False),
        ("App::PropertyLength", "WireStretchLength", 0.0),
    ]:
        config.addProperty(prop_type, name, "", "")
        setattr(config, name, value)
    job.ConfigName = config.Name

    wpl = job.newObject("Part::FeaturePython", "WPL")
    wpl.addProperty("App::PropertyString", "Type", "", "")
    wpl.Type = "Helper"
    for prop_type, name, value in [
        ("App::PropertyLength", "Length", 870.0),
        ("App::PropertyLength", "Width", 330.0),
        ("App::PropertyPosition", "Position", App.Vector(-370.0, -304.8, 0.0)),
    ]:
        wpl.addProperty(prop_type, name, "", "")
        setattr(wpl, name, value)
    job.WPLName = wpl.Name

    wpr = job.newObject("Part::FeaturePython", "WPR")
    wpr.addProperty("App::PropertyString", "Type", "", "")
    wpr.Type = "Helper"
    for prop_type, name, value in [
        ("App::PropertyLength", "Length", 870.0),
        ("App::PropertyLength", "Width", 330.0),
        ("App::PropertyPosition", "Position", App.Vector(370.0, -304.8, 0.0)),
    ]:
        wpr.addProperty(prop_type, name, "", "")
        setattr(wpr, name, value)
    job.WPRName = wpr.Name

    path = job.newObject("App::FeaturePython", "Path")
    path.addProperty("App::PropertyString", "Type", "", "")
    path.addProperty("App::PropertyString", "JobName", "", "")
    path.Type = "Path"
    path.JobName = job.Name
    path.addProperty("App::PropertyLength", "DiscretizationStep", "", "")
    path.setExpression(".DiscretizationStep", "<<Config>>.DiscretizationStep")
    doc.recompute()
    return doc, job


class TestMigration(unittest.TestCase):
    def tearDown(self):
        App.closeDocument(App.ActiveDocument.Name)

    def test_migrates_config_and_helpers_in_one_pass(self):
        doc, job = make_old_document()
        self.assertEqual(Migration.migrate_document(doc), 1)

        self.assertIsNone(doc.getObject("Config"))
        self.assertIsNone(doc.getObject("WPL"))
        self.assertIsNone(doc.getObject("WPR"))
        self.assertAlmostEqual(float(job.FieldWidth), 740.0, places=5)
        self.assertAlmostEqual(float(job.PauseDuration), 1.0, places=5)
        self.assertEqual(job.ConfigName, "")
        self.assertEqual(job.WPLName, "")
        self.assertEqual(job.WPRName, "")
        self.assertEqual(job.MigrationVersion, Migration.CURRENT_VERSION)

        path = doc.getObject("Path")
        self.assertEqual(
            path.ExpressionEngine[0][1],
            "._Job.DiscretizationStep")

    def test_migration_is_idempotent(self):
        doc, job = make_old_document()
        self.assertEqual(Migration.migrate_document(doc), 1)
        self.assertEqual(Migration.migrate_document(doc), 0)

    def test_custom_working_plane_is_preserved(self):
        doc, job = make_old_document()
        Migration.migrate_document(doc)
        self.assertTrue(job.WorkingPlaneCustom)
        self.assertAlmostEqual(float(job.WorkingPlaneY), -304.8, places=5)

        left = utilities.getWorkingPlanes(job, doc)[0]
        self.assertAlmostEqual(float(left.Position.y), -304.8, places=5)

    def test_failed_migration_leaves_document_unchanged(self):
        doc, job = make_old_document()
        original = Migration._copy_config_properties

        def fail(*args, **kwargs):
            raise RuntimeError("migration test failure")

        Migration._copy_config_properties = fail
        try:
            with self.assertRaises(RuntimeError):
                Migration.migrate_document(doc)
        finally:
            Migration._copy_config_properties = original

        self.assertIsNotNone(doc.getObject("Config"))
        self.assertFalse(hasattr(job, "MigrationVersion"))


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
