# -*- coding: utf-8 -*-
"""Offset-wire join regression tests.

The route offset builder joins adjacent edge offsets by intersecting their
end/start edges.  When two offsets have different magnitudes (dynamic kerf
compensation) the wires may miss each other: the line-extension intersection
can lie alongside the second wire instead of beyond its end.  Extending in
that case prepends a point that reverses the wire, and the spline resampling
turns that cusp into a visible loop.

The first test uses a sliced real-world case: the leading-edge junction of
the ``left_wing`` route (Path004 -> Path005) from the reported document,
projected to the temporary plane used by WireRoute.

Run with:
    FreeCADCmd.exe tests/test_offset_join.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

from utilities import connectWires, intersectWires, makeWire

X = -304.8


def wire(points):
    return makeWire([App.Vector(X, y, z) for (y, z) in points])


def turn_deg(a, b, c):
    u = b - a
    v = c - b
    if u.Length <= 1e-12 or v.Length <= 1e-12:
        return 0.0
    return u.getAngle(v) * 180.0 / 3.141592653589793


class TestMissedOffsetJoin(unittest.TestCase):
    """Path004 offset ends 0.22 mm short of Path005 offset.

    The supporting-line intersection lies 0.60 mm along Path005's offset
    and only 0.031 mm off it.  It must trim Path005, not extend it.
    """

    def setUp(self):
        # Last edge of Path004's compensated offset (left/short side).
        self.wire1 = wire([
            (310.379435, 40.602551),
            (310.415216, 40.36722),
        ])
        # Start of Path005's compensated offset, same junction.
        self.wire2 = wire([
            (310.498002, 40.165332),
            (310.514121, 39.921793),
            (310.508290, 39.576524),
            (310.474981, 39.236776),
            (310.414872, 38.901806),
            (310.328075, 38.572288),
            (310.218938, 38.261524),
            (310.098479, 37.983342),
            (309.971309, 37.731678),
            (309.836587, 37.497412),
            (309.695594, 37.278302),
            (309.549741, 37.073154),
            # tail of the real wire, keeps it a long polyline
            (275.205025, 32.926764),
        ])

    def test_second_wire_is_trimmed_not_extended(self):
        point, mode1, mode2 = intersectWires(self.wire1, self.wire2, 5e-3)
        self.assertEqual(mode1, "extend",
                         "first wire should be extended to the intersection")
        self.assertEqual(mode2, "trim",
                         "second wire should be trimmed: intersection is "
                         "inside its span, 0.031 mm off the curve")

    def test_joined_wire_does_not_reverse_at_start(self):
        point, mode1, mode2 = intersectWires(self.wire1, self.wire2, 5e-3)
        _, joined = connectWires(self.wire1, self.wire2, (point, mode1, mode2))
        verts = [v.Point for v in joined.Vertexes]
        self.assertGreaterEqual(len(verts), 3)
        # A prepended intersection point would make the first turn ~180 deg.
        self.assertLess(
            turn_deg(verts[0], verts[1], verts[2]), 90.0,
            "joined wire starts with a reversal: %s -> %s -> %s" % (
                verts[0], verts[1], verts[2]))

    def test_joined_wire_keeps_first_turns_within_90_degrees(self):
        point, mode1, mode2 = intersectWires(self.wire1, self.wire2, 5e-3)
        _, joined = connectWires(self.wire1, self.wire2, (point, mode1, mode2))
        verts = [v.Point for v in joined.Vertexes]
        for i in range(1, min(6, len(verts) - 1)):
            self.assertLess(
                turn_deg(verts[i - 1], verts[i], verts[i + 1]), 90.0,
                "joined wire reverses at vertex %d: %s" % (i, verts[i]))


class TestOffsetJoinOutsideLimit(unittest.TestCase):
    """Transverse offsets that only meet by extension keep working.

    Mirrors ``Test cases/Offset intersections/intersection outside limits``:
    the horizontal wire ends 0.6 mm before the vertical wire; the vertical
    wire must be trimmed, the horizontal one extended.
    """

    def test_horizontal_extends_vertical_trims(self):
        horizontal = wire([(8.0, 119.4), (460.0, 119.4)])
        vertical = wire([(460.6, 120.0), (460.6, 0.0)])
        point, mode1, mode2 = intersectWires(horizontal, vertical, 5e-3)
        self.assertAlmostEqual(point.y, 460.6, places=6)
        self.assertAlmostEqual(point.z, 119.4, places=6)
        self.assertEqual((mode1, mode2), ("extend", "trim"))


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
