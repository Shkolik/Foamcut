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
        config = self.job.getObject(self.job.ConfigName)
        for prop_type, name, value in [
            ("App::PropertyTime", "PauseDuration", 1.0),
            ("App::PropertyLength", "DiscretizationStep", 0.5),
            ("App::PropertySpeed", "FeedRateCut", 2.66),
            ("App::PropertyInteger", "WireMinPower", 860),
            ("App::PropertyBool", "WireStretchVerification", False),
            ("App::PropertyLength", "WireStretchLength", 0.0),
            ("App::PropertyDistance", "OriginRotationX", 370.0),
        ]:
            ensure(config, prop_type, name, value)
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
        self.assertTrue(hasattr(WireMove, "createMove"))
        self.assertTrue(hasattr(WireEnter, "createEnter"))
        self.assertTrue(hasattr(WireExit, "createExit"))
        self.assertTrue(hasattr(WireJoin, "createJoin"))
        self.assertTrue(hasattr(WirePath, "createPath"))
        self.assertTrue(hasattr(WireProjection, "createProjection"))
        self.assertTrue(hasattr(Rotate, "createRotation"))
        self.assertTrue(hasattr(WireRoute, "createRoute"))

    def _edge_on_plane(self, x):
        for index, edge in enumerate(self.box.Shape.Edges):
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


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
