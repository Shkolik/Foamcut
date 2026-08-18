# -*- coding: utf-8 -*-
"""Fast-path trim edge index tests. Run via FreeCADCmd.exe tests/test_trim_fast_path.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import Part
from utilities import _pointSegmentDistanceSq, findTrimEdgeIndex, makeWire, trimOrExtendWire


def polyline_wire(n, step=10.0):
    pts = [FreeCAD.Vector(i * step, 0.0, 0.0) for i in range(n + 1)]
    return makeWire(pts)


class TestPointSegmentDistance(unittest.TestCase):
    def test_point_on_segment(self):
        a = FreeCAD.Vector(0, 0, 0)
        b = FreeCAD.Vector(10, 0, 0)
        self.assertAlmostEqual(_pointSegmentDistanceSq(FreeCAD.Vector(5, 0, 0), a, b), 0.0, places=6)

    def test_point_at_endpoint(self):
        a = FreeCAD.Vector(0, 0, 0)
        b = FreeCAD.Vector(10, 0, 0)
        self.assertAlmostEqual(_pointSegmentDistanceSq(FreeCAD.Vector(10, 3, 0), a, b), 9.0, places=6)

    def test_point_off_segment(self):
        a = FreeCAD.Vector(0, 0, 0)
        b = FreeCAD.Vector(10, 0, 0)
        self.assertAlmostEqual(_pointSegmentDistanceSq(FreeCAD.Vector(5, 4, 0), a, b), 16.0, places=6)

    def test_zero_length_segment(self):
        a = FreeCAD.Vector(2, 2, 2)
        self.assertAlmostEqual(_pointSegmentDistanceSq(FreeCAD.Vector(2, 2, 5), a, a), 9.0, places=6)


class TestFindTrimEdgeIndex(unittest.TestCase):
    def reference_index(self, wire, point):
        vertex = Part.Vertex(point)
        (_, _, infos) = vertex.distToShape(wire)
        (_, _, _, topo2, index2, _) = infos[0]
        if topo2 != "Edge":
            raise Exception("Trim expected intersection on edge.")
        return index2

    def test_point_on_middle_segment(self):
        wire = polyline_wire(50)  # segments 0..49, vertices at x = 0..500
        point = FreeCAD.Vector(475.0, 0.0, 0.0)  # interior of segment 47 (x 470..480)
        self.assertEqual(findTrimEdgeIndex(wire, point), 47)

    def test_point_on_last_segment(self):
        wire = polyline_wire(50)
        point = FreeCAD.Vector(499.0, 0.0, 0.0)
        self.assertEqual(findTrimEdgeIndex(wire, point), 49)

    def test_point_on_first_segment(self):
        wire = polyline_wire(50)
        point = FreeCAD.Vector(1.0, 0.0, 0.0)
        self.assertEqual(findTrimEdgeIndex(wire, point), 0)

    def test_equivalence_with_occ_reference_on_wire(self):
        wire = polyline_wire(50)
        for point in (FreeCAD.Vector(1.0, 0.0, 0.0), FreeCAD.Vector(125.0, 0.0, 0.0),
                      FreeCAD.Vector(475.0, 0.0, 0.0), FreeCAD.Vector(499.0, 0.0, 0.0)):
            self.assertEqual(findTrimEdgeIndex(wire, point), self.reference_index(wire, point))

    def test_slightly_off_wire_point_falls_back_and_matches_occ(self):
        wire = polyline_wire(50)
        point = FreeCAD.Vector(235.0, 0.001, 0.0)  # > 1e-4 off wire -> OCC fallback
        self.assertEqual(findTrimEdgeIndex(wire, point), self.reference_index(wire, point))

    def test_point_on_shared_vertex_returns_lower_index(self):
        wire = polyline_wire(50)
        point = FreeCAD.Vector(50.0, 0.0, 0.0)  # vertex 5, shared by segments 4 and 5
        self.assertEqual(findTrimEdgeIndex(wire, point), 4)


class TestTrimOrientation(unittest.TestCase):
    def test_trim_end(self):
        wire = polyline_wire(50)
        point = FreeCAD.Vector(475.0, 0.0, 0.0)
        res = trimOrExtendWire(wire, point, "trim", "end")
        self.assertAlmostEqual(res.Vertexes[-1].Point.x, 475.0, places=6)
        self.assertEqual(len(res.Vertexes), 49)  # edges 0..46 kept (vertices 0..47) + appended endpoint

    def test_trim_start(self):
        wire = polyline_wire(50)
        point = FreeCAD.Vector(25.0, 0.0, 0.0)
        res = trimOrExtendWire(wire, point, "trim", "start")
        self.assertAlmostEqual(res.Vertexes[0].Point.x, 25.0, places=6)


class TestTrimLargeWire(unittest.TestCase):
    def test_trim_end_preserves_vertices(self):
        wire = polyline_wire(260)  # segments 0..259, vertices at x = 0..2600
        point = FreeCAD.Vector(2505.0, 0.0, 0.0)  # interior of segment 250 (x 2500..2510)
        res = trimOrExtendWire(wire, point, "trim", "end")
        verts = res.Vertexes
        self.assertEqual(len(verts), 252)  # edges 0..249 kept (vertices 0..250) + appended endpoint
        for i, v in enumerate(verts[:-1]):
            self.assertAlmostEqual(v.Point.x, i * 10.0, places=6)
        self.assertAlmostEqual(verts[-1].Point.x, 2505.0, places=6)

    def test_trim_start_preserves_vertices(self):
        wire = polyline_wire(260)
        point = FreeCAD.Vector(55.0, 0.0, 0.0)  # interior of segment 5 (x 50..60)
        res = trimOrExtendWire(wire, point, "trim", "start")
        verts = res.Vertexes
        self.assertEqual(len(verts), 256)  # edges 6..259 kept (vertices 6..260) + appended endpoint
        self.assertAlmostEqual(verts[0].Point.x, 55.0, places=6)
        for i, v in enumerate(verts[1:], start=6):
            self.assertAlmostEqual(v.Point.x, i * 10.0, places=6)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
