# -*- coding: utf-8 -*-
"""Opposite-vertex resolution tests for Enter/Exit selections.

Covers selecting a Path plane vertex as well as an original-edge vertex on
either side, with an inverted right edge.

Run via FreeCADCmd.exe tests/test_opposite_vertex.py
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
import WireExit
import WirePath
from test_route_postprocess import new_document


def make_inverted_path(doc, job):
    '''Path whose right edge is stored in the opposite direction.'''
    wires = doc.addObject("Part::Feature", "Wires")
    wires.Shape = Part.makeCompound([
        Part.makeLine(App.Vector(-100.0, 0.0, 0.0), App.Vector(-100.0, 10.0, 0.0)),
        Part.makeLine(App.Vector(100.0, 20.0, 0.0), App.Vector(100.0, 0.0, 0.0)),
    ])
    doc.recompute()
    path = WirePath.createPath(job, (wires, "Edge1"), (wires, "Edge2"), recompute = False)
    doc.recompute()
    return path


def make_crossed_path(doc, job):
    '''Path whose selected edges swap sides, so the projection is tied.'''
    wires = doc.addObject("Part::Feature", "Wires")
    wires.Shape = Part.makeCompound([
        Part.makeLine(App.Vector(100.0, 0.0, 0.0), App.Vector(100.0, 10.0, 0.0)),
        Part.makeLine(App.Vector(-100.0, 20.0, 0.0), App.Vector(-100.0, 0.0, 0.0)),
    ])
    doc.recompute()
    path = WirePath.createPath(job, (wires, "Edge1"), (wires, "Edge2"), recompute = False)
    doc.recompute()
    return path


class TestOppositeVertex(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()
        self.path = make_inverted_path(self.doc, self.job)
        self.assertEqual(self.path.EdgesInverted, True)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def check_exit(self, vertex_name, expected_left, expected_right):
        exit_obj = WireExit.createExit(self.job, (self.path, vertex_name), recompute = False)
        exit_obj.LeadOutEnabled = False
        exit_obj.touch()
        self.doc.recompute()

        self.assertAlmostEqual(exit_obj.ExitPointL.x, expected_left[0], places = 5)
        self.assertAlmostEqual(exit_obj.ExitPointL.y, expected_left[1], places = 5)
        self.assertAlmostEqual(exit_obj.ExitPointR.x, expected_right[0], places = 5)
        self.assertAlmostEqual(exit_obj.ExitPointR.y, expected_right[1], places = 5)

    def test_left_plane_start_vertex(self):
        # - Path_L start is the left start / right end wire.
        self.check_exit("Vertex1", (-100.0, 0.0), (100.0, 0.0))

    def test_left_plane_end_vertex(self):
        # - Path_L end is the left end / right start wire.
        self.check_exit("Vertex2", (-100.0, 10.0), (100.0, 20.0))

    def test_right_plane_start_vertex(self):
        # - Path_R start is the left start / right end wire.
        self.check_exit("Vertex3", (-100.0, 0.0), (100.0, 0.0))

    def test_right_plane_end_vertex(self):
        # - Path_R end is the left end / right start wire.
        self.check_exit("Vertex4", (-100.0, 10.0), (100.0, 20.0))

    def test_original_left_start_vertex(self):
        self.check_exit("Vertex5", (-100.0, 0.0), (100.0, 0.0))

    def test_original_left_end_vertex(self):
        self.check_exit("Vertex6", (-100.0, 10.0), (100.0, 20.0))

    def test_original_right_start_vertex(self):
        self.check_exit("Vertex7", (-100.0, 10.0), (100.0, 20.0))

    def test_original_right_end_vertex(self):
        self.check_exit("Vertex8", (-100.0, 0.0), (100.0, 0.0))


class TestCrossedOppositeVertex(unittest.TestCase):
    '''Edges swap sides, so the path end must follow the wire line, not the index.'''

    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()
        self.path = make_crossed_path(self.doc, self.job)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def resolve(self, vertex_name):
        vertex = self.path.getSubObject(vertex_name)
        (isLeft, vertex, opposite, _) = self.path.Proxy.findOppositeVertexes(
            self.path, self.path, vertex)
        return (isLeft, vertex.Point, opposite.Point)

    def test_left_start_follows_the_right_edge(self):
        (_, vertex, opposite) = self.resolve("Vertex1")
        self.assertAlmostEqual(vertex.x, -100.0, places = 5)
        self.assertAlmostEqual(vertex.y, 0.0, places = 5)
        self.assertAlmostEqual(opposite.x, 100.0, places = 5)
        self.assertAlmostEqual(opposite.y, 0.0, places = 5)

    def test_left_end_follows_the_right_edge(self):
        (_, vertex, opposite) = self.resolve("Vertex2")
        self.assertAlmostEqual(vertex.x, -100.0, places = 5)
        self.assertAlmostEqual(vertex.y, 20.0, places = 5)
        self.assertAlmostEqual(opposite.x, 100.0, places = 5)
        self.assertAlmostEqual(opposite.y, 10.0, places = 5)

    def test_right_start_follows_the_left_edge(self):
        (_, vertex, opposite) = self.resolve("Vertex3")
        self.assertAlmostEqual(vertex.x, 100.0, places = 5)
        self.assertAlmostEqual(vertex.y, 0.0, places = 5)
        self.assertAlmostEqual(opposite.x, -100.0, places = 5)
        self.assertAlmostEqual(opposite.y, 0.0, places = 5)

    def test_right_end_follows_the_left_edge(self):
        (_, vertex, opposite) = self.resolve("Vertex4")
        self.assertAlmostEqual(vertex.x, 100.0, places = 5)
        self.assertAlmostEqual(vertex.y, 10.0, places = 5)
        self.assertAlmostEqual(opposite.x, -100.0, places = 5)
        self.assertAlmostEqual(opposite.y, 20.0, places = 5)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity = 2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
