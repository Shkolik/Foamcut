# -*- coding: utf-8 -*-
"""Route clone (duplicate/place/mirror) tests. Run via FreeCADCmd.exe tests/test_route_clone.py"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import utilities
import WireRoute
from test_g93 import generate, make_config
from test_route_postprocess import (add_movement, build_route, new_document,
                                    ensure, has_dest, parse_blocks, all_moves)

CUT_HEIGHT = 2.0
LEAD_HEIGHT = CUT_HEIGHT + 6.0
SAFE_HEIGHT = 120.0
PIVOT = 25.0


def new_clone_document():
    doc, job = new_document()
    config = job.getObject(job.ConfigName)
    ensure(config, "App::PropertyLength", "BlockHeight", 50.0)
    ensure(config, "App::PropertyPosition", "BlockPosition", App.Vector(0.0, 0.0, 0.0))
    return doc, job


def make_objects(doc):
    objects = [
        add_movement(doc, "Enter", "Enter",
                     [(5.0, LEAD_HEIGHT), (10.0, CUT_HEIGHT)], lead=True),
        add_movement(doc, "Path", "Path", [(10.0, CUT_HEIGHT), (20.0, CUT_HEIGHT)]),
        add_movement(doc, "Exit", "Exit",
                     [(20.0, CUT_HEIGHT), (25.0, LEAD_HEIGHT)], lead=True, rapid=True),
    ]
    # asymmetric wire ends so YZ plane swapping is observable
    for obj in objects:
        obj.Path_R = [App.Vector(0.0, point.y + 3.0, point.z) for point in obj.Path_L]
    return objects


def dest(points_L, points_R, index):
    return (points_L[index].y, points_L[index].z, points_R[index].y, points_R[index].z)


class TestRouteLayoutAndMirror(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_clone_document()
        self.route = build_route(self.doc, self.job, make_objects(self.doc))

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_route_point_layout(self):
        # plunge, lead-in | entry | exit, lead-out, plunge-up
        blocks = WireRoute.getRoutePointLayout(self.route)
        self.assertEqual([(block[0].Label, block[1], block[2]) for block in blocks],
                         [("Enter", 0, 2), ("Path", 2, 1), ("Exit", 3, 3)])
        self.assertEqual(len(self.route.Offset_L), 6)

    def test_mirror_xy_keeps_plunges_and_rebuilds_leads(self):
        mirrored = WireRoute.mirrorRoutePointsXY(self.route, list(self.route.Offset_L), PIVOT)

        mirrored_entry = 2.0 * PIVOT - CUT_HEIGHT          # 48
        lead_offset = LEAD_HEIGHT - CUT_HEIGHT             # 6

        self.assertAlmostEqual(mirrored[0].z, SAFE_HEIGHT)                   # plunge stays safe
        self.assertAlmostEqual(mirrored[1].z, mirrored_entry + lead_offset)  # Enter lead rebuilt
        self.assertAlmostEqual(mirrored[2].z, mirrored_entry)                # entry mirrored
        self.assertAlmostEqual(mirrored[3].z, mirrored_entry)                # exit mirrored
        self.assertAlmostEqual(mirrored[4].z, mirrored_entry + lead_offset)  # Exit lead rebuilt
        self.assertAlmostEqual(mirrored[5].z, SAFE_HEIGHT)                   # plunge-up stays safe

    def test_original_route_protocol(self):
        proxy = self.route.Proxy
        self.assertIsInstance(proxy, WireRoute.WireRoute)
        self.assertIs(proxy.getSourceRoute(self.route), self.route)
        points_L, points_R = proxy.getOutputPoints(self.route)
        self.assertEqual(points_L, list(self.route.Offset_L))
        self.assertEqual(points_R, list(self.route.Offset_R))
        self.assertEqual(proxy.getRotationAngle(self.route, 90.0), 90.0)


import WireRouteClone


def add_clone(doc, job, source):
    clone = doc.addObject("App::FeaturePython", "RouteClone")
    WireRouteClone.WireRouteClone(clone, source, job.Name)
    return clone


class TestRouteCloneObject(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_clone_document()
        self.route = build_route(self.doc, self.job, make_objects(self.doc))
        self.clone = add_clone(self.doc, self.job, self.route)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_clone_type_source_defaults(self):
        self.assertEqual(self.clone.Type, "RouteClone")
        self.assertEqual(self.clone.Proxy.getSourceRoute(self.clone).Name, self.route.Name)
        self.assertEqual(tuple(self.clone.Position), (0.0, 0.0, 0.0))
        self.assertEqual(self.clone.Mirror, "None")
        self.assertEqual(self.clone.JobName, self.job.Name)
        self.assertFalse(hasattr(self.clone, "Offset_L"))

    def test_clone_points_match_source(self):
        points_L, points_R = self.clone.Proxy.getOutputPoints(self.clone)
        self.assertEqual(points_L, list(self.route.Offset_L))
        self.assertEqual(points_R, list(self.route.Offset_R))

    def test_clone_follows_source_changes(self):
        before = self.clone.Proxy.getOutputPoints(self.clone)
        exit_obj = self.doc.getObjectsByLabel("Exit")[0]
        exit_obj.Path_L = [App.Vector(0.0, 20.0, CUT_HEIGHT), App.Vector(0.0, 25.0, 10.0)]
        exit_obj.Path_R = [App.Vector(0.0, 23.0, CUT_HEIGHT), App.Vector(0.0, 28.0, 10.0)]
        self.doc.recompute()

        after = self.clone.Proxy.getOutputPoints(self.clone)
        self.assertNotEqual(before, after, "clone did not follow the source route")
        self.assertEqual(after, self.route.Proxy.getOutputPoints(self.route))

    def test_mirror_yz_property_swaps_profiles_on_each_plane(self):
        self.clone.Mirror = "YZ"
        self.doc.recompute()
        clone_L, clone_R = self.clone.Proxy.getOutputPoints(self.clone)
        source_L, source_R = self.route.Proxy.getOutputPoints(self.route)

        self.assertEqual([point.x for point in clone_L], [point.x for point in source_L])
        self.assertEqual([point.x for point in clone_R], [point.x for point in source_R])
        for left, right in zip(clone_L, source_R):
            self.assertAlmostEqual(left.y, right.y)
            self.assertAlmostEqual(left.z, right.z)
        for left, right in zip(clone_R, source_L):
            self.assertAlmostEqual(left.y, right.y)
            self.assertAlmostEqual(left.z, right.z)

    def test_mirror_xy_keeps_plunges_and_rebuilds_leads(self):
        self.clone.Mirror = "XY"
        self.doc.recompute()
        clone_L, _ = self.clone.Proxy.getOutputPoints(self.clone)

        mirrored_entry = 2.0 * PIVOT - CUT_HEIGHT          # 48
        lead_offset = LEAD_HEIGHT - CUT_HEIGHT             # 6

        self.assertAlmostEqual(clone_L[0].z, SAFE_HEIGHT)
        self.assertAlmostEqual(clone_L[1].z, mirrored_entry + lead_offset)
        self.assertAlmostEqual(clone_L[2].z, mirrored_entry)
        self.assertAlmostEqual(clone_L[3].z, mirrored_entry)
        self.assertAlmostEqual(clone_L[4].z, mirrored_entry + lead_offset)
        self.assertAlmostEqual(clone_L[5].z, SAFE_HEIGHT)

    def test_mirror_combined(self):
        self.clone.Mirror = "YZ+XY"
        self.doc.recompute()
        clone_L, clone_R = self.clone.Proxy.getOutputPoints(self.clone)
        source_L, _ = self.route.Proxy.getOutputPoints(self.route)
        self.assertEqual(len(clone_L), len(source_L))
        self.assertAlmostEqual(clone_L[0].z, SAFE_HEIGHT)
        self.assertAlmostEqual(clone_L[2].z, 2.0 * PIVOT - CUT_HEIGHT)
        self.assertAlmostEqual(clone_R[2].z, 2.0 * PIVOT - CUT_HEIGHT)

    def test_mirror_reverses_rotation_angle(self):
        self.assertEqual(self.clone.Proxy.getRotationAngle(self.clone, 90.0), 90.0)
        for mode in ("YZ", "XY", "YZ+XY"):
            self.clone.Mirror = mode
            self.assertEqual(self.clone.Proxy.getRotationAngle(self.clone, 90.0), -90.0)

    def test_position_is_applied(self):
        WireRouteClone.setRoutePosition(self.clone, App.Vector(0.0, 12.5, 3.0))
        self.assertAlmostEqual(self.clone.Position.y, 12.5)
        points_L, _ = self.clone.Proxy.getOutputPoints(self.clone)
        self.assertAlmostEqual(points_L[0].y, self.route.Offset_L[0].y + 12.5)
        self.assertAlmostEqual(points_L[0].z, self.route.Offset_L[0].z + 3.0)

    def test_position_is_validated_against_working_area(self):
        with self.assertRaises(Exception):
            WireRouteClone.setRoutePosition(self.clone, App.Vector(0.0, 1e6, 0.0))
        self.assertEqual(tuple(self.clone.Position), (0.0, 0.0, 0.0))

    def test_clone_of_clone_is_refused(self):
        second = self.doc.addObject("App::FeaturePython", "RouteClone2")
        with self.assertRaises(Exception):
            WireRouteClone.WireRouteClone(second, self.clone, self.job.Name)

    def test_clone_without_source_is_inert(self):
        self.clone.Source = None
        self.clone.Proxy.execute(self.clone)  # must not raise
        with self.assertRaises(Exception):
            self.clone.Proxy.getOutputPoints(self.clone)

    def test_non_route_source_is_refused(self):
        join = add_movement(self.doc, "Join", "Join", [(0.0, CUT_HEIGHT)])
        self.clone.Source = join
        with self.assertRaises(Exception):
            self.clone.Proxy.getOutputPoints(self.clone)

    def test_source_from_another_job_is_refused(self):
        original_job = self.route.JobName
        try:
            self.route.JobName = "OtherJob"
            with self.assertRaises(Exception) as context:
                self.clone.Proxy.getOutputPoints(self.clone)
            self.assertIn("another job", str(context.exception))
        finally:
            self.route.JobName = original_job

    def test_can_duplicate_route(self):
        self.assertTrue(WireRouteClone.canDuplicateRoute(self.route))
        self.assertFalse(WireRouteClone.canDuplicateRoute(self.clone))
        self.assertFalse(WireRouteClone.canDuplicateRoute(None))


def make_rotation_objects(doc):
    rotation = add_movement(doc, "Rotation", "Rotation", [(30.0, CUT_HEIGHT)])
    rotation.addProperty("App::PropertyAngle", "Angle", "Task", "")
    rotation.Angle = 90.0
    return [
        add_movement(doc, "Enter", "Enter", [(5.0, CUT_HEIGHT), (10.0, CUT_HEIGHT)], lead=True),
        add_movement(doc, "Path", "Path", [(10.0, CUT_HEIGHT), (20.0, CUT_HEIGHT)]),
        add_movement(doc, "Exit", "Exit", [(20.0, CUT_HEIGHT), (25.0, CUT_HEIGHT)], lead=True),
        rotation,
        add_movement(doc, "Enter", "Enter001", [(35.0, CUT_HEIGHT), (40.0, CUT_HEIGHT)], lead=True),
        add_movement(doc, "Path", "Path001", [(40.0, CUT_HEIGHT), (50.0, CUT_HEIGHT)]),
        add_movement(doc, "Exit", "Exit001", [(50.0, CUT_HEIGHT), (55.0, CUT_HEIGHT)], lead=True),
    ]


class TestRouteClonePostprocess(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = make_config(utilities.FC_FEED_RATE_MODES[0])
        cls.outpath = os.path.join(tempfile.gettempdir(), "route_clone_test.gcode")

    def setUp(self):
        self.doc, self.job = new_clone_document()
        self.route = build_route(self.doc, self.job, make_objects(self.doc))
        self.clone = add_clone(self.doc, self.job, self.route)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def moves(self, routes):
        return all_moves(parse_blocks(generate(self.config, routes, self.outpath)))

    def test_zero_position_emits_same_moves(self):
        base = self.moves([self.route])
        clone_moves = self.moves([self.clone])
        self.assertEqual([m.dest for m in base], [m.dest for m in clone_moves])

    def test_position_is_applied_by_postprocessor(self):
        dy, dz = 12.5, 3.0
        self.clone.Position = App.Vector(0.0, dy, dz)
        self.doc.recompute()

        base = self.moves([self.route])
        moved = self.moves([self.clone])
        self.assertEqual(len(base), len(moved))
        for original, clone_move in zip(base, moved):
            self.assertAlmostEqual(clone_move.dest[0], original.dest[0] + dy, places=1)
            self.assertAlmostEqual(clone_move.dest[1], original.dest[1] + dz, places=1)
            self.assertAlmostEqual(clone_move.dest[2], original.dest[2] + dy, places=1)
            self.assertAlmostEqual(clone_move.dest[3], original.dest[3] + dz, places=1)

    def test_mirror_yz_swaps_planes_in_gcode(self):
        self.clone.Mirror = "YZ"
        self.doc.recompute()

        base = self.moves([self.route])
        mirrored = self.moves([self.clone])
        self.assertEqual(len(base), len(mirrored))
        for original, mirror_move in zip(base, mirrored):
            self.assertAlmostEqual(mirror_move.dest[0], original.dest[2], places=2)
            self.assertAlmostEqual(mirror_move.dest[1], original.dest[3], places=2)
            self.assertAlmostEqual(mirror_move.dest[2], original.dest[0], places=2)
            self.assertAlmostEqual(mirror_move.dest[3], original.dest[1], places=2)

    def test_mirror_xy_keeps_plunges_and_rebuilds_leads_in_gcode(self):
        self.clone.Mirror = "XY"
        self.doc.recompute()

        points_L, points_R = self.clone.Proxy.getOutputPoints(self.clone)
        blocks = parse_blocks(generate(self.config, [self.clone], self.outpath))
        enter_block, path_block, exit_block = blocks

        for index in (0, 1, 2):
            self.assertIsNotNone(has_dest(enter_block, dest(points_L, points_R, index)),
                                 "Enter block lost route point {}".format(index))
        self.assertIsNotNone(has_dest(path_block, dest(points_L, points_R, 3)))
        for index in (4, 5):
            self.assertIsNotNone(has_dest(exit_block, dest(points_L, points_R, index)),
                                 "Exit block lost route point {}".format(index))

        mirrored_entry = 2.0 * PIVOT - CUT_HEIGHT
        lead_offset = LEAD_HEIGHT - CUT_HEIGHT
        self.assertAlmostEqual(points_L[0].z, SAFE_HEIGHT)
        self.assertAlmostEqual(points_L[1].z, mirrored_entry + lead_offset)
        self.assertAlmostEqual(points_L[4].z, mirrored_entry + lead_offset)
        self.assertAlmostEqual(points_L[5].z, SAFE_HEIGHT)

        for move in all_moves(blocks):
            if move.command == "G00":
                self.assertGreaterEqual(move.dest[1], SAFE_HEIGHT - 1e-6)
                self.assertGreaterEqual(move.dest[3], SAFE_HEIGHT - 1e-6)

    def test_mixed_route_and_clone_are_both_emitted(self):
        self.clone.Position = App.Vector(0.0, 40.0, 0.0)
        self.doc.recompute()
        content = generate(self.config, [self.route, self.clone], self.outpath)
        self.assertIn("--- Route begin [Route] ---", content)
        self.assertIn("--- Route begin [RouteClone] ---", content)
        self.assertIn("--- Route end [RouteClone] ---", content)
        single = len(self.moves([self.route]))
        # The second route's begin-rapid is parsed into the previous route's last block,
        # because it is emitted before that route's first object comment.
        self.assertEqual(len(all_moves(parse_blocks(content))), 2 * single + 1)

    def test_clone_triggers_stale_source_refresh(self):
        expected = len(self.route.Offset_L)
        self.route.Offset_L = list(self.route.Offset_L) + [self.route.Offset_L[-1]]
        self.route.Offset_R = list(self.route.Offset_R) + [self.route.Offset_R[-1]]
        generate(self.config, [self.clone], self.outpath)
        self.assertEqual(len(self.route.Offset_L), expected)


class TestRouteCloneRotation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = make_config(utilities.FC_FEED_RATE_MODES[0])
        cls.outpath = os.path.join(tempfile.gettempdir(), "route_clone_rotation.gcode")

    def setUp(self):
        self.doc, self.job = new_clone_document()
        self.route = build_route(self.doc, self.job, make_rotation_objects(self.doc))
        self.clone = add_clone(self.doc, self.job, self.route)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_mirror_reverses_rotation_in_gcode(self):
        plain = generate(self.config, [self.route], self.outpath)
        self.assertIn("B90.00", plain)

        for mode in ("YZ", "XY", "YZ+XY"):
            self.clone.Mirror = mode
            self.doc.recompute()
            mirrored = generate(self.config, [self.clone], self.outpath)
            self.assertIn("B-90.00", mirrored)


class TestRouteCloneScripting(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_clone_document()
        self.route = build_route(self.doc, self.job, make_objects(self.doc))
        self.job.addObject(self.route)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_create_route_clone_in_job(self):
        clone = WireRouteClone.createRouteClone(self.job, self.route)
        self.assertEqual(clone.Type, "RouteClone")
        self.assertEqual(clone.Label, "{}_clone".format(self.route.Label))
        self.assertEqual(clone.JobName, self.job.Name)
        self.assertIn(clone, self.job.Group)
        self.assertEqual(clone.Proxy.getSourceRoute(clone).Name, self.route.Name)

    def test_create_route_clone_custom_label(self):
        clone = WireRouteClone.createRouteClone(self.job, self.route, label = "Custom")
        self.assertEqual(clone.Label, "Custom")

    def test_create_route_clone_requires_route(self):
        join = add_movement(self.doc, "Join", "Join", [(0.0, CUT_HEIGHT)])
        with self.assertRaises(Exception):
            WireRouteClone.createRouteClone(self.job, join)

    def test_create_route_clone_requires_same_job(self):
        original_job = self.route.JobName
        try:
            self.route.JobName = "OtherJob"
            with self.assertRaises(Exception):
                WireRouteClone.createRouteClone(self.job, self.route)
        finally:
            self.route.JobName = original_job

    def test_get_job_routes(self):
        routes = WireRouteClone.getJobRoutes(self.job)
        self.assertEqual([route.Name for route in routes], [self.route.Name])


class TestRouteCloneGuiSurface(unittest.TestCase):
    def test_gui_module_exposes_ui(self):
        import RouteCloneGui
        self.assertTrue(hasattr(RouteCloneGui, "WireRouteCloneVP"))
        self.assertTrue(hasattr(RouteCloneGui, "RouteCloneTaskPanel"))
        self.assertTrue(hasattr(RouteCloneGui, "DuplicateRoute"))
        self.assertTrue(callable(RouteCloneGui.showRouteClonePanel))


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
