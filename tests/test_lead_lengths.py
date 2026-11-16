# -*- coding: utf-8 -*-
"""Lead-in / lead-out proportional length tests.

Run via FreeCADCmd.exe tests/test_lead_lengths.py
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
import utilities
import WireEnter
import WireExit
import WirePath
from test_route_postprocess import ensure, new_document


def make_path(doc, job, left_length, right_length):
    '''Build a Path from two line edges of different lengths on the planes.'''
    wires = doc.addObject("Part::Feature", "Wires")
    wires.Shape = Part.makeCompound([
        Part.makeLine(App.Vector(-370.0, 0.0, 0.0), App.Vector(-370.0, left_length, 0.0)),
        Part.makeLine(App.Vector(370.0, 0.0, 0.0), App.Vector(370.0, right_length, 0.0)),
    ])
    doc.recompute()
    path = WirePath.createPath(job, (wires, "Edge1"), (wires, "Edge2"), recompute = False)
    doc.recompute()
    return path


def raw_pair(proxy, obj, parent, vertex_name):
    '''Return the original-edge (left, right) points used for the lead.'''
    vertex = parent.getSubObject(vertex_name)
    result = proxy.findOppositeVertexes(obj, parent, vertex)
    is_left, point, opposite, _ = result
    if is_left:
        return (point.Point, opposite.Point)
    return (opposite.Point, point.Point)


class TestParallelEdgeLength(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()
        self.obj = self.doc.addObject("App::FeaturePython", "RuledPath")
        ensure(self.obj, "App::PropertyString", "JobName", self.job.Name)
        ensure(self.obj, "App::PropertyVectorList", "Path_L")
        ensure(self.obj, "App::PropertyVectorList", "Path_R")
        ensure(self.obj, "App::PropertyBool", "EdgesInverted", False)
        self.obj.Path_L = [App.Vector(-370.0, 0.0, 0.0), App.Vector(-370.0, 10.0, 0.0)]
        self.obj.Path_R = [App.Vector(370.0, 0.0, 0.0), App.Vector(370.0, 10.0, 0.0)]

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_inverted_flag_does_not_reverse_wire_pairing(self):
        '''Path_L[i] and Path_R[i] are the same wire; EdgesInverted must not swap them.'''
        for inverted in (False, True):
            with self.subTest(inverted = inverted):
                self.obj.EdgesInverted = inverted
                self.assertAlmostEqual(
                    utilities.getParallelEdgeLength(self.obj, 0.0), 10.0, places = 4)

    def test_project_edge_to_plane_returns_points_and_length(self):
        from MachinePlane import WorkingPlane
        plane = WorkingPlane.fromX(self.job, 0.0)
        projected, length = utilities.projectEdgeToPlane(
            self.obj.Path_L, self.obj.Path_R, plane)

        self.assertAlmostEqual(length, 10.0, places = 4)
        self.assertEqual(len(projected), 2)
        for point in projected:
            self.assertAlmostEqual(point.x, 0.0, places = 6)
        self.assertAlmostEqual(projected[0].y, 0.0, places = 6)
        self.assertAlmostEqual(projected[1].y, 10.0, places = 6)

    def test_project_edge_to_plane_rejects_mismatched_point_counts(self):
        from MachinePlane import WorkingPlane
        plane = WorkingPlane.fromX(self.job, 0.0)
        with self.assertRaises(Exception):
            utilities.projectEdgeToPlane(self.obj.Path_L, self.obj.Path_R[:-1], plane)

    def test_spline_length_handles_short_point_lists(self):
        self.assertEqual(utilities.getSplineLength([]), 0.0)
        self.assertEqual(utilities.getSplineLength([App.Vector(0.0, 0.0, 0.0)]), 0.0)


class TestLeadScales(unittest.TestCase):
    def test_short_side_keeps_nominal_scale(self):
        self.assertEqual(utilities.getLeadScales(10.0, 20.0), (1.0, 2.0))
        self.assertEqual(utilities.getLeadScales(20.0, 10.0), (2.0, 1.0))

    def test_equal_or_unknown_lengths_are_unscaled(self):
        self.assertEqual(utilities.getLeadScales(10.0, 10.0), (1.0, 1.0))
        self.assertEqual(utilities.getLeadScales(0.0, 20.0), (1.0, 1.0))
        self.assertEqual(utilities.getLeadScales(20.0, 0.0), (1.0, 1.0))


class TestLeadProportions(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def scales(self, path):
        left = utilities.getParallelEdgeLength(path, -370.0)
        right = utilities.getParallelEdgeLength(path, 370.0)
        return utilities.getLeadScales(left, right)

    def check_lead(self, obj_type, left_length, right_length, lead):
        path = make_path(self.doc, self.job, left_length, right_length)
        left_scale, right_scale = self.scales(path)

        if obj_type == "Enter":
            obj = WireEnter.createEnter(self.job, (path, "Vertex1"), recompute = False)
            obj.LeadInX = lead
            vertex_name = "Vertex1"
        else:
            obj = WireExit.createExit(self.job, (path, "Vertex2"), recompute = False)
            obj.LeadOutX = lead
            vertex_name = "Vertex2"

        obj.touch()
        self.doc.recompute()

        left_point, right_point = raw_pair(obj.Proxy, obj, path, vertex_name)
        if obj_type == "Enter":
            actual_left = obj.EntryPointL
            actual_right = obj.EntryPointR
        else:
            actual_left = obj.ExitPointL
            actual_right = obj.ExitPointR

        # - The shorter side keeps the nominal lead length, the longer side is
        #   scaled by its length ratio.
        self.assertAlmostEqual(actual_left.y - left_point.y, lead * left_scale, places = 4)
        self.assertAlmostEqual(actual_right.y - right_point.y, lead * right_scale, places = 4)
        self.assertAlmostEqual(min(left_scale, right_scale), 1.0, places = 6)

    def test_enter_short_left(self):
        self.check_lead("Enter", 10.0, 20.0, -5.0)

    def test_enter_short_right(self):
        self.check_lead("Enter", 20.0, 10.0, -5.0)

    def test_exit_short_right(self):
        self.check_lead("Exit", 20.0, 10.0, -5.0)

    def test_exit_short_left(self):
        self.check_lead("Exit", 10.0, 20.0, -5.0)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity = 2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
