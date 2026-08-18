# -*- coding: utf-8 -*-
"""Working area boundary validation tests. Run via FreeCADCmd.exe tests/test_working_area.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import utilities


def make_plane(pos, length, width):
    p = type("Plane", (), {})()
    p.Position = FreeCAD.Vector(*pos)
    p.Length = length
    p.Width = width
    return p


WPL = make_plane((0.0, 0.0, 0.0), 500.0, 300.0)   # y in [0,500], z in [0,300]
WPR = make_plane((0.0, 100.0, 0.0), 500.0, 300.0)  # y in [100,600], z in [0,300]


def pt(x, y, z):
    return FreeCAD.Vector(x, y, z)


class TestInside(unittest.TestCase):
    def test_all_points_inside_passes(self):
        L = [pt(-370, 20, 120), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 580, 10)]
        self.assertIsNone(utilities.validateWorkingArea(L, R, WPL, WPR))

    def test_empty_point_list_passes(self):
        self.assertIsNone(utilities.validateWorkingArea([], [], WPL, WPR))

    def test_point_exactly_on_boundary_passes(self):
        L = [pt(-370, 0, 0), pt(-370, 500, 300)]
        R = [pt(370, 100, 0), pt(370, 600, 300)]
        self.assertIsNone(utilities.validateWorkingArea(L, R, WPL, WPR))


class TestHorizontalTravel(unittest.TestCase):
    def test_maxY_beyond_upper_edge_raises(self):
        L = [pt(-370, 20, 120), pt(-370, 500.001, 10)]
        R = [pt(370, 120, 120), pt(370, 580, 10)]
        with self.assertRaises(Exception) as ctx:
            utilities.validateWorkingArea(L, R, WPL, WPR)
        self.assertEqual(
            "horizontal travel exceed machine boundary on a left plane. Adjust model position.",
            str(ctx.exception))

    def test_minY_below_lower_edge_raises(self):
        # OriginX may be 0/negative/positive, so the lower Y edge matters
        L = [pt(-370, -0.001, 120), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 580, 10)]
        with self.assertRaises(Exception):
            utilities.validateWorkingArea(L, R, WPL, WPR)

    def test_right_plane_violation_names_right(self):
        L = [pt(-370, 20, 120), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 600.001, 10)]
        with self.assertRaises(Exception) as ctx:
            utilities.validateWorkingArea(L, R, WPL, WPR)
        self.assertIn("right plane", str(ctx.exception))


class TestVerticalTravel(unittest.TestCase):
    def test_maxZ_beyond_upper_edge_raises(self):
        L = [pt(-370, 20, 120), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 580, 300.001)]
        with self.assertRaises(Exception) as ctx:
            utilities.validateWorkingArea(L, R, WPL, WPR)
        self.assertIn("vertical travel", str(ctx.exception))
        self.assertIn("right plane", str(ctx.exception))

    def test_minZ_below_lower_edge_raises(self):
        L = [pt(-370, 20, -0.001), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 580, 10)]
        with self.assertRaises(Exception):
            utilities.validateWorkingArea(L, R, WPL, WPR)


class TestTolerance(unittest.TestCase):
    def test_outside_tolerance_raises(self):
        L = [pt(-370, 20, 120), pt(-370, 500.0001, 10)]  # > 1e-7 over
        R = [pt(370, 120, 120), pt(370, 580, 10)]
        with self.assertRaises(Exception):
            utilities.validateWorkingArea(L, R, WPL, WPR)


class TestQuantityUnits(unittest.TestCase):
    """Real FreeCAD planes return Quantity for Length/Width - must not raise
    'Unit mismatch in plus operation'."""

    def make_quantity_plane(self, pos, length, width):
        p = type("Plane", (), {})()
        p.Position = FreeCAD.Vector(*pos)
        p.Length = FreeCAD.Units.Quantity("%f mm" % length)
        p.Width = FreeCAD.Units.Quantity("%f mm" % width)
        return p

    def test_quantity_planes_inside_passes(self):
        wpl = self.make_quantity_plane((0.0, 0.0, 0.0), 500.0, 300.0)
        wpr = self.make_quantity_plane((0.0, 100.0, 0.0), 500.0, 300.0)
        L = [pt(-370, 20, 120), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 580, 10)]
        self.assertIsNone(utilities.validateWorkingArea(L, R, wpl, wpr))

    def test_quantity_planes_outside_raises(self):
        wpl = self.make_quantity_plane((0.0, 0.0, 0.0), 500.0, 300.0)
        wpr = self.make_quantity_plane((0.0, 100.0, 0.0), 500.0, 300.0)
        L = [pt(-370, 20, 120), pt(-370, 480, 10)]
        R = [pt(370, 120, 120), pt(370, 600.001, 10)]
        with self.assertRaises(Exception) as ctx:
            utilities.validateWorkingArea(L, R, wpl, wpr)
        self.assertIn("right plane", str(ctx.exception))


# FreeCADCmd imports the passed script as a module, so also run when entry script.
if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)