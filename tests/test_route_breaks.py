# -*- coding: utf-8 -*-
"""Route break accounting and polyline splitting tests.

The route view provider draws one polyline per route segment. Break indexes
must point at the last point of the segment (the end of an Exit lead-out),
otherwise a cut segment disappears from the 3D view while the G-code stays
correct.

Run via FreeCADCmd.exe tests/test_route_breaks.py
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

import RouteGui
import WireRoute
from test_route_postprocess import add_movement, build_route, new_document


def make_sub_route(doc, y):
    '''Enter + cut + Exit forming one continuous sub-route at machine Y.'''
    return [
        add_movement(doc, "Enter", "Enter", [(y, 122.0)]),
        add_movement(doc, "Move", "Move", [(y, 72.0), (y, 122.0)]),
        add_movement(doc, "Exit", "Exit", [(y, 72.0), (y - 5.0, 72.0)], lead = True),
    ]


def make_two_sub_routes(doc, rotation = None):
    objects = []
    if rotation == "start":
        objects.append(add_movement(doc, "Rotation", "Rotation", []))
    objects += make_sub_route(doc, 315.0)
    if rotation == "middle":
        objects.append(add_movement(doc, "Rotation", "Rotation", []))
    objects += make_sub_route(doc, 445.0)
    return objects


def group_ranges(points, groups):
    '''Return (start, end) point indexes for consecutive point groups.'''
    ranges = []
    index = 0
    for group in groups:
        ranges.append((index, index + len(group) - 1))
        index += len(group)
    return ranges


class TestRouteBreaks(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_document()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def build(self, objects):
        route = build_route(self.doc, self.job, objects)
        self.assertGreater(len(route.Offset_L), 0)
        return route

    def test_single_segment_route_has_no_breaks(self):
        route = self.build(make_sub_route(self.doc, 315.0))

        self.assertEqual(len(route.Offset_L), 5)
        self.assertEqual(list(route.RouteBreaks), [])
        self.assertEqual(WireRoute.getRouteBreaks(route), [])

    def test_two_sub_routes_break_at_the_exit_lead_out(self):
        route = self.build(make_two_sub_routes(self.doc))

        self.assertEqual(len(route.Offset_L), 10)
        # - first Exit ends at point 4; the rapid to the second sub-route
        #   starts at point 5.
        self.assertEqual(list(route.RouteBreaks), [4])
        self.assertEqual(WireRoute.getRouteBreaks(route), [4])

        groups = RouteGui.splitRoutePoints(route.Offset_L, route.RouteBreaks)
        self.assertEqual(group_ranges(route.Offset_L, groups), [(0, 4), (5, 9)])
        self.assertEqual(sum(len(group) for group in groups), len(route.Offset_L))

    def test_rotation_first_route_has_no_leading_break(self):
        route = self.build(make_two_sub_routes(self.doc, rotation = "start"))

        self.assertEqual(len(route.Offset_L), 10)
        # - A rotation before the first Enter has no previous point to break at.
        self.assertEqual(list(route.RouteBreaks), [4])
        groups = RouteGui.splitRoutePoints(route.Offset_L, route.RouteBreaks)
        self.assertEqual(group_ranges(route.Offset_L, groups), [(0, 4), (5, 9)])

    def test_mid_route_rotation_breaks_at_the_exit(self):
        route = self.build(make_two_sub_routes(self.doc, rotation = "middle"))

        self.assertEqual(list(route.RouteBreaks), [4])
        groups = RouteGui.splitRoutePoints(route.Offset_L, route.RouteBreaks)
        self.assertEqual(group_ranges(route.Offset_L, groups), [(0, 4), (5, 9)])

    def test_three_sub_routes_break_after_each_exit(self):
        objects = make_sub_route(self.doc, 315.0)
        objects += make_sub_route(self.doc, 445.0)
        objects += make_sub_route(self.doc, 575.0)
        route = self.build(objects)

        self.assertEqual(list(route.RouteBreaks), [4, 9])
        self.assertEqual(WireRoute.getRouteBreaks(route), [4, 9])
        groups = RouteGui.splitRoutePoints(route.Offset_L, route.RouteBreaks)
        self.assertEqual(group_ranges(route.Offset_L, groups), [(0, 4), (5, 9), (10, 14)])

    def test_trailing_rotation_has_no_break(self):
        objects = make_sub_route(self.doc, 315.0)
        objects.append(add_movement(self.doc, "Rotation", "Rotation", []))
        route = self.build(objects)

        self.assertEqual(list(route.RouteBreaks), [])
        self.assertEqual(WireRoute.getRouteBreaks(route), [])

    def test_trailing_rotation_with_kerf_compensation(self):
        objects = make_sub_route(self.doc, 315.0)
        objects += make_sub_route(self.doc, 445.0)
        objects.append(add_movement(self.doc, "Rotation", "Rotation", []))

        for strategy in ("Uniform", "Dynamic"):
            with self.subTest(strategy = strategy):
                route = build_route(self.doc, self.job, objects, kerf = 0.5, strategy = strategy)

                self.assertEqual(len(route.Offset_L), 10)
                self.assertEqual(list(route.RouteBreaks), [4])

    def test_rotation_at_both_ends_with_kerf_compensation(self):
        objects = make_two_sub_routes(self.doc, rotation = "start")
        objects.append(add_movement(self.doc, "Rotation", "Rotation001", []))
        route = build_route(self.doc, self.job, objects, kerf = 0.7, strategy = "Uniform")

        self.assertEqual(len(route.Offset_L), 10)
        self.assertEqual(list(route.RouteBreaks), [4])
        self.assertEqual(WireRoute.getRouteBreaks(route), [4])

    def test_split_points_keeps_every_cut_segment(self):
        route = self.build(make_two_sub_routes(self.doc))
        points = list(route.Offset_L)

        groups = RouteGui.splitRoutePoints(points, [4])

        self.assertEqual([[tuple(p) for p in group] for group in groups],
                         [[tuple(p) for p in points[0:5]], [tuple(p) for p in points[5:10]]])

    def test_view_provider_ignores_stale_stored_breaks(self):
        route = self.build(make_two_sub_routes(self.doc))
        route.RouteBreaks = [2]  # - value stored by older builds

        provider = RouteGui.WireRouteVP.__new__(RouteGui.WireRouteVP)
        provider.Object = route

        self.assertEqual(provider.routeBreaks(), [4])


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity = 2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
