# -*- coding: utf-8 -*-
"""Scripting factory tests. Run via FreeCADCmd.exe tests/test_object_factories.py"""

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
import Rotate
import WireMove
import WireEnter
import WireExit
import WireJoin
import WirePath
import WireProjection
import WireRoute
from test_route_postprocess import ensure, new_document


class TestScriptingFactories(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_document()
        for prop_type, name, value in [
            ("App::PropertyTime", "PauseDuration", 1.0),
            ("App::PropertyLength", "DiscretizationStep", 0.5),
            ("App::PropertySpeed", "FeedRateCut", 2.66),
            ("App::PropertyInteger", "WireMinPower", 860),
            ("App::PropertyBool", "WireStretchVerification", False),
            ("App::PropertyLength", "WireStretchLength", 0.0),
            ("App::PropertyDistance", "OriginRotationX", 370.0),
        ]:
            ensure(self.job, prop_type, name, value)
        self.doc.recompute()

        self.box = self.doc.addObject("Part::Box", "Box")
        self.box.Length = 740.0
        self.box.Width = 200.0
        self.box.Height = 100.0
        self.box.Placement.Base = App.Vector(-370.0, -100.0, 50.0)
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_factories_are_exposed(self):
        self.assertTrue(hasattr(InitMachine, "createMachine"))
        self.assertTrue(hasattr(WireMove, "createMove"))
        self.assertTrue(hasattr(WireEnter, "createEnter"))
        self.assertTrue(hasattr(WireExit, "createExit"))
        self.assertTrue(hasattr(WireJoin, "createJoin"))
        self.assertTrue(hasattr(WirePath, "createPath"))
        self.assertTrue(hasattr(WireProjection, "createProjection"))
        self.assertTrue(hasattr(Rotate, "createRotation"))
        self.assertTrue(hasattr(WireRoute, "createRoute"))

    def test_create_machine_inside_document(self):
        doc = App.newDocument("MachineFactory")
        try:
            job = InitMachine.createMachine(doc, label = "Setup A", recompute = False)

            self.assertEqual(job.Type, "Job")
            self.assertEqual(job.Label, "Setup A")
            self.assertIs(job.Document, doc)
            self.assertIn(job, doc.Objects)
            self.assertTrue(hasattr(job, "FieldWidth"))
        finally:
            App.closeDocument(doc.Name)

    def _edge_on_plane(self, x, obj = None):
        obj = obj if obj is not None else self.box
        for index, edge in enumerate(obj.Shape.Edges):
            if all(abs(vertex.Point.x - x) < 1e-6 for vertex in edge.Vertexes):
                return index + 1
        raise AssertionError("edge not found on x={}".format(x))

    def test_create_path_inside_job(self):
        left = (self.box, "Edge{}".format(self._edge_on_plane(-370.0)))
        right = (self.box, "Edge{}".format(self._edge_on_plane(370.0)))

        path = WirePath.createPath(self.job, left, right, recompute = False)

        self.assertEqual(path.Type, "Path")
        self.assertIn(path, self.job.Group)
        self.assertGreater(len(path.Path_L), 0)
        self.assertGreater(len(path.Path_R), 0)

    def test_create_rotation_inside_job(self):
        rotation = Rotate.createRotation(self.job, self.box, recompute = False)

        self.assertEqual(rotation.Type, "Rotation")
        self.assertIn(rotation, self.job.Group)
        self.assertGreater(rotation.Shape.Volume, 0)

    def test_path_and_projection_expose_kerf_direction(self):
        left = (self.box, "Edge{}".format(self._edge_on_plane(-370.0)))
        right = (self.box, "Edge{}".format(self._edge_on_plane(370.0)))
        path = WirePath.createPath(self.job, left, right, recompute = False)
        projection = WireProjection.createProjection(self.job, (self.box, "Edge1"), recompute = False)
        self.doc.recompute()

        for obj in (path, projection):
            mode = obj.getEditorMode("CompensationDirection")
            self.assertNotIn("Hidden", mode)
            self.assertNotIn("ReadOnly", mode)
            self.assertEqual(obj.CompensationDirection, "Normal")
            obj.CompensationDirection = "Reversed"
            self.assertEqual(obj.CompensationDirection, "Reversed")

    def test_old_path_and_projection_unhide_kerf_direction(self):
        left = (self.box, "Edge{}".format(self._edge_on_plane(-370.0)))
        right = (self.box, "Edge{}".format(self._edge_on_plane(370.0)))
        path = WirePath.createPath(self.job, left, right, recompute = False)
        projection = WireProjection.createProjection(self.job, (self.box, "Edge1"), recompute = False)

        for obj in (path, projection):
            obj.setEditorMode("CompensationDirection", 3)
            self.assertIn("Hidden", obj.getEditorMode("CompensationDirection"))

            obj.Proxy.onDocumentRestored(obj)

            mode = obj.getEditorMode("CompensationDirection")
            self.assertNotIn("Hidden", mode)
            self.assertNotIn("ReadOnly", mode)

    def test_objects_bind_to_the_selected_setup(self):
        doc = App.newDocument("TwoSetups")
        try:
            first = InitMachine.createMachine(doc, label = "Setup A", recompute = False)
            second = InitMachine.createMachine(doc, label = "Setup B", recompute = False)

            box = doc.addObject("Part::Box", "Box")
            box.Length = 740.0
            box.Width = 200.0
            box.Height = 100.0
            box.Placement.Base = App.Vector(-370.0, -100.0, 50.0)
            doc.recompute()

            left = (box, "Edge{}".format(self._edge_on_plane(-370.0, box)))
            right = (box, "Edge{}".format(self._edge_on_plane(370.0, box)))

            path_a = WirePath.createPath(first, left, right, recompute = False)
            path_b = WirePath.createPath(second, left, right, recompute = False)
            doc.recompute()

            self.assertIn(path_a, first.Group)
            self.assertNotIn(path_a, second.Group)
            self.assertIn(path_b, second.Group)
            self.assertIs(path_a._Job, first)
            self.assertIs(path_b._Job, second)
        finally:
            App.closeDocument(doc.Name)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
