# -*- coding: utf-8 -*-
"""Route point-allocation regression tests.

These tests exercise the real WireRoute offset builder and the real
Postprocess G-code emitter for routes made of Enter / movement / Exit
objects.  They deliberately assert geometry- and safety-level properties,
not the exact number of generated lines, so they survive changes that
remove redundant duplicate points.

Run with:
    FreeCADCmd.exe tests/test_route_postprocess.py
"""

import os
import re
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

import FoamCut_WorkingPlane
import JobConfig
import Postprocess
import utilities
import WireRoute
from test_g93 import generate, make_config

SAFE_HEIGHT = 120.0
CUT_HEIGHT = 2.0
EPS = 1e-6

BLOCK_RE = re.compile(r"^; - (\w+) \[(.*?)\]")
MOVE_RE = re.compile(
    r"^(G0[01])\s+"
    r"X(-?\d+(?:\.\d+)?)\s+"
    r"Y(-?\d+(?:\.\d+)?)\s+"
    r"Z(-?\d+(?:\.\d+)?)\s+"
    r"A(-?\d+(?:\.\d+)?)"
)


def vec(y, z):
    return App.Vector(0.0, y, z)


def ensure(obj, ptype, name, default=None, group=""):
    if not hasattr(obj, name):
        obj.addProperty(ptype, name, group, "")
    if default is not None:
        setattr(obj, name, default)


def add_movement(doc, obj_type, label, path, lead=False, rapid=False):
    """Create a generic movement object with a straight L/R path.

    The route builder only needs the movement contract (Type, Path_L/R,
    PointsCount, lead flags, RapidMove), not the concrete Enter/Exit proxy.
    """
    obj = doc.addObject("Part::FeaturePython", "Obj")
    obj.Label = label
    ensure(obj, "App::PropertyString", "Type", obj_type)
    ensure(obj, "App::PropertyBool", "LeadInEnabled", lead)
    ensure(obj, "App::PropertyBool", "LeadOutEnabled", lead)
    ensure(obj, "App::PropertyBool", "RapidMove", rapid)
    ensure(obj, "App::PropertyInteger", "PointsCount", len(path))
    ensure(obj, "App::PropertyVectorList", "Path_L", [vec(y, z) for y, z in path])
    ensure(obj, "App::PropertyVectorList", "Path_R", [vec(y, z) for y, z in path])
    ensure(obj, "App::PropertyFloat", "FeedRate", 3.0)
    ensure(obj, "App::PropertyFloat", "WirePower", 700.0)
    ensure(obj, "App::PropertyBool", "AddPause", False)
    ensure(obj, "App::PropertyFloat", "PauseDuration", 0.0)
    ensure(obj, "App::PropertyString", "CompensationDirection", "Normal")
    ensure(obj, "App::PropertyFloat", "LeftEdgeLength", 1.0)
    ensure(obj, "App::PropertyFloat", "RightEdgeLength", 1.0)
    ensure(obj, "App::PropertyFloat", "LeftSegmentLength", 1.0)
    ensure(obj, "App::PropertyFloat", "RightSegmentLength", 1.0)
    ensure(obj, "App::PropertyLength", "SafeHeight", SAFE_HEIGHT)
    return obj


def new_document():
    doc = App.newDocument("RoutePP")
    job = doc.addObject("App::DocumentObjectGroupPython", "Job")
    ensure(job, "App::PropertyString", "Type", "Job")
    job.Type = "Job"

    JobConfig.applyConfigProperties(job)
    job.FieldWidth = 740.0
    job.HorizontalTravel = 870.0
    job.VerticalTravel = 330.0
    job.OriginX = 0.0
    job.KerfCompensation = 0.0
    job.CompensationDegree = 1.0

    return doc, job


def build_route(doc, job, objects, kerf=0.0, strategy=None):
    job.KerfCompensation = kerf
    route = doc.addObject("Part::FeaturePython", "Route")
    WireRoute.WireRoute(route, objects, job.Name)
    if strategy is not None:
        route.CompensationStrategy = strategy
    if kerf > 0 and strategy not in (None, "None"):
        # Kerf compensation is read from the Job expression, so let the
        # document resolve expressions before executing the route.
        doc.recompute()
    else:
        route.Proxy.execute(route)
    return route


class Move(object):
    def __init__(self, command, dest):
        self.command = command
        self.dest = dest


class Block(object):
    def __init__(self, obj_type, label):
        self.obj_type = obj_type
        self.label = label
        self.moves = []


def parse_blocks(gcode):
    blocks = []
    current = None
    for line in gcode.splitlines():
        match = BLOCK_RE.match(line)
        if match:
            current = Block(match.group(1), match.group(2))
            blocks.append(current)
            continue
        match = MOVE_RE.match(line)
        if match and current is not None:
            current.moves.append(Move(
                match.group(1),
                (float(match.group(2)), float(match.group(3)),
                 float(match.group(4)), float(match.group(5)))
            ))
    return blocks


def all_moves(blocks):
    return [move for block in blocks for move in block.moves]


def dest_for(route, index):
    left = route.Offset_L[index]
    right = route.Offset_R[index]
    return (left.y, left.z, right.y, right.z)


def has_dest(block, dest):
    for move in block.moves:
        if all(abs(a - b) < EPS for a, b in zip(move.dest, dest)):
            return move
    return None


class RoutePointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = make_config(utilities.FC_FEED_RATE_MODES[0])
        cls.outpath = os.path.join(tempfile.gettempdir(), "route_points_test.gcode")

    def _route(self, doc, job, objects):
        route = build_route(doc, job, objects)
        return route, parse_blocks(generate(self.config, [route], self.outpath))

    def _assert_all_points_consumed(self, route, blocks):
        moves = all_moves(blocks)
        self.assertTrue(moves, "route generated no motion commands")
        expected = dest_for(route, len(route.Offset_L) - 1)
        self.assertEqual(
            moves[-1].dest, expected,
            "route end point was not emitted: last move %s, expected %s "
            "(route has %d offset points)" % (
                moves[-1].dest, expected, len(route.Offset_L))
        )

    def _assert_no_rapid_in_foam(self, blocks):
        for move in all_moves(blocks):
            if move.command != "G00":
                continue
            self.assertGreaterEqual(
                move.dest[1], SAFE_HEIGHT - EPS,
                "rapid move to cut height (left wire end): %s" % (move.dest,))
            self.assertGreaterEqual(
                move.dest[3], SAFE_HEIGHT - EPS,
                "rapid move to cut height (right wire end): %s" % (move.dest,))

    def _assert_cut(self, block, point, message):
        move = has_dest(block, point)
        self.assertIsNotNone(
            move, "%s: no move to %s in %s [%s]; moves=%s" % (
                message, point, block.obj_type, block.label,
                [m.dest for m in block.moves]))
        self.assertEqual(
            move.command, "G01",
            "%s: move to %s was %s, expected G01 (cut); moves=%s" % (
                message, point, move.command,
                [(m.command, m.dest) for m in block.moves]))

    def test_single_point_enters_between_rapid_exits(self):
        """Enter(no lead-in) -> Exit -> Enter(no lead-in) -> Exit.

        Regression for the route where every Enter has exactly one point,
        the Exit is a rapid move and the next Enter is swallowed by the
        previous Exit block.  The last route point must be emitted and no
        rapid may enter the foam.
        """
        doc, job = new_document()
        try:
            objects = [
                add_movement(doc, "Enter", "Enter", [(10.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit",
                             [(10.0, CUT_HEIGHT), (15.0, CUT_HEIGHT)],
                             lead=True, rapid=True),
                add_movement(doc, "Enter", "Enter001", [(30.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit001",
                             [(30.0, CUT_HEIGHT), (35.0, CUT_HEIGHT)],
                             lead=True, rapid=True),
            ]
            route, blocks = self._route(doc, job, objects)

            self._assert_all_points_consumed(route, blocks)
            self._assert_no_rapid_in_foam(blocks)

            enters = [b for b in blocks if b.obj_type == "Enter"]
            self.assertEqual(len(enters), 2,
                             "expected two Enter blocks, got %s" %
                             [(b.obj_type, b.label) for b in blocks])
            self.assertTrue(enters[1].moves,
                            "second Enter block has no motion commands")
            self._assert_cut(
                enters[1], (30.0, CUT_HEIGHT, 30.0, CUT_HEIGHT),
                "second Enter must emit its own entry point as a cut")
            self.assertEqual(
                enters[1].moves[0].command, "G00",
                "Exit->Enter connection at safe height must be rapid; "
                "first move of second Enter is %s" %
                enters[1].moves[0].command)
        finally:
            App.closeDocument(doc.Name)

    def test_enter_middle_exit_all_lead_and_rapid_combinations(self):
        """Enter -> Path/Projection/Move -> Exit over every flag combination."""
        for middle_type in ("Path", "Projection", "Move"):
            for lead_in in (False, True):
                for lead_out in (False, True):
                    for enter_rapid in (False, True):
                        for exit_rapid in (False, True):
                            label = "%s leadIn=%s leadOut=%s enterRapid=%s exitRapid=%s" % (
                                middle_type, lead_in, lead_out,
                                enter_rapid, exit_rapid)
                            with self.subTest(label):
                                self._run_combination(
                                    middle_type, lead_in, lead_out,
                                    enter_rapid, exit_rapid, label)

    def _run_combination(self, middle_type, lead_in, lead_out,
                         enter_rapid, exit_rapid, label):
        doc, job = new_document()
        try:
            enter_path = [(5.0, CUT_HEIGHT), (10.0, CUT_HEIGHT)] \
                if lead_in else [(10.0, CUT_HEIGHT)]
            exit_path = [(20.0, CUT_HEIGHT), (25.0, CUT_HEIGHT)] \
                if lead_out else [(20.0, CUT_HEIGHT)]

            objects = [
                add_movement(doc, "Enter", "Enter", enter_path,
                             lead=lead_in, rapid=enter_rapid),
                add_movement(doc, middle_type, middle_type,
                             [(10.0, CUT_HEIGHT), (20.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit", exit_path,
                             lead=lead_out, rapid=exit_rapid),
            ]
            route, blocks = self._route(doc, job, objects)

            self._assert_all_points_consumed(route, blocks)
            self._assert_no_rapid_in_foam(blocks)

            self.assertEqual([b.obj_type for b in blocks],
                             ["Enter", middle_type, "Exit"],
                             "%s: unexpected block sequence" % label)
            enter_block, middle_block, exit_block = blocks

            self._assert_cut(
                enter_block,
                (10.0, CUT_HEIGHT, 10.0, CUT_HEIGHT),
                "%s: Enter entry point" % label)
            if lead_in:
                self._assert_cut(
                    enter_block,
                    (5.0, CUT_HEIGHT, 5.0, CUT_HEIGHT),
                    "%s: Enter lead-in point" % label)

            self._assert_cut(
                middle_block,
                (20.0, CUT_HEIGHT, 20.0, CUT_HEIGHT),
                "%s: middle object end point" % label)

            if lead_out:
                self._assert_cut(
                    exit_block,
                    (25.0, CUT_HEIGHT, 25.0, CUT_HEIGHT),
                    "%s: Exit lead-out point" % label)
                self.assertEqual(
                    has_dest(exit_block,
                             (25.0, SAFE_HEIGHT, 25.0, SAFE_HEIGHT)) is not None,
                    True, "%s: Exit must finish with a move to safe height" % label)
            else:
                self.assertEqual(
                    has_dest(exit_block,
                             (20.0, SAFE_HEIGHT, 20.0, SAFE_HEIGHT)) is not None,
                    True, "%s: Exit must finish with a move to safe height" % label)
        finally:
            App.closeDocument(doc.Name)

    def test_exit_with_kerf_compensation_has_no_duplicate_endpoint(self):
        """Compensated Exit must still end at the lead-out point, not duplicate it."""
        for strategy in ("Uniform", "Dynamic"):
            for exit_rapid in (False, True):
                label = "%s exitRapid=%s" % (strategy, exit_rapid)
                with self.subTest(label):
                    self._run_compensated_exit(strategy, exit_rapid, label)

    def _run_compensated_exit(self, strategy, exit_rapid, label):
        doc, job = new_document()
        try:
            objects = [
                add_movement(doc, "Enter", "Enter",
                             [(5.0, CUT_HEIGHT), (10.0, CUT_HEIGHT)],
                             lead=True, rapid=False),
                add_movement(doc, "Path", "Path",
                             [(10.0, CUT_HEIGHT), (20.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit",
                             [(20.0, CUT_HEIGHT), (25.0, CUT_HEIGHT)],
                             lead=True, rapid=exit_rapid),
            ]
            route = build_route(doc, job, objects, kerf=0.7, strategy=strategy)
            self.assertGreater(
                float(route.KerfCompensation), 0.0,
                "%s: kerf compensation was not applied to the route" % label)

            blocks = parse_blocks(generate(self.config, [route], self.outpath))
            self._assert_all_points_consumed(route, blocks)
            self._assert_no_rapid_in_foam(blocks)

            exit_block = [b for b in blocks if b.obj_type == "Exit"][0]
            self.assertTrue(exit_block.moves,
                            "%s: Exit block has no motion commands" % label)

            for previous, current in zip(exit_block.moves, exit_block.moves[1:]):
                self.assertFalse(
                    all(abs(a - b) < EPS for a, b in zip(previous.dest, current.dest)),
                    "%s: Exit block contains a duplicate move to %s" %
                    (label, current.dest))

            last = exit_block.moves[-1]
            self.assertGreaterEqual(
                last.dest[1], SAFE_HEIGHT - EPS,
                "%s: Exit must finish at safe height, got %s" % (label, last.dest))

            lead_out = [m for m in exit_block.moves
                        if abs(m.dest[0] - 25.0) < EPS
                        and m.dest[1] < SAFE_HEIGHT - EPS]
            self.assertTrue(
                lead_out,
                "%s: Exit lead-out point was not emitted; moves=%s" %
                (label, [(m.command, m.dest) for m in exit_block.moves]))
            self.assertEqual(
                lead_out[0].command, "G01",
                "%s: Exit lead-out must be a cut, got %s" %
                (label, lead_out[0].command))
        finally:
            App.closeDocument(doc.Name)

    def test_stale_exit_point_layout_is_refreshed(self):
        """Routes saved with the old duplicate Exit point are recomputed on use."""
        doc, job = new_document()
        try:
            objects = [
                add_movement(doc, "Enter", "Enter",
                             [(5.0, CUT_HEIGHT), (10.0, CUT_HEIGHT)], lead=True),
                add_movement(doc, "Path", "Path",
                             [(10.0, CUT_HEIGHT), (20.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit",
                             [(20.0, CUT_HEIGHT), (25.0, CUT_HEIGHT)],
                             lead=True, rapid=True),
            ]
            route = build_route(doc, job, objects)

            # Simulate a document stored by the old builder: one duplicate
            # Exit end point at the end of the flattened route.
            route.Offset_L = list(route.Offset_L) + [route.Offset_L[-1]]
            route.Offset_R = list(route.Offset_R) + [route.Offset_R[-1]]
            stale_length = len(route.Offset_L)

            blocks = parse_blocks(generate(self.config, [route], self.outpath))
            self.assertEqual(
                len(route.Offset_L), stale_length - 1,
                "stale route point layout was not refreshed")

            self._assert_all_points_consumed(route, blocks)
            exit_block = [b for b in blocks if b.obj_type == "Exit"][0]
            for previous, current in zip(exit_block.moves, exit_block.moves[1:]):
                self.assertFalse(
                    all(abs(a - b) < EPS for a, b in zip(previous.dest, current.dest)),
                    "refreshed Exit block still contains a duplicate move to %s" %
                    (current.dest,))
        finally:
            App.closeDocument(doc.Name)

    def test_exit_to_enter_connection_is_always_rapid(self):
        """The travel from an Exit plunge-up to the next Enter plunge-down is
        performed at safe height and must be rapid regardless of RapidMove."""
        for enter_rapid in (False, True):
            for exit_rapid in (False, True):
                label = "enterRapid=%s exitRapid=%s" % (enter_rapid, exit_rapid)
                with self.subTest(label):
                    self._run_exit_enter(enter_rapid, exit_rapid, label)

    def _run_exit_enter(self, enter_rapid, exit_rapid, label):
        doc, job = new_document()
        try:
            objects = [
                add_movement(doc, "Enter", "Enter",
                             [(5.0, CUT_HEIGHT), (10.0, CUT_HEIGHT)],
                             lead=True, rapid=enter_rapid),
                add_movement(doc, "Path", "Path",
                             [(10.0, CUT_HEIGHT), (20.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit",
                             [(20.0, CUT_HEIGHT), (25.0, CUT_HEIGHT)],
                             lead=True, rapid=exit_rapid),
                add_movement(doc, "Enter", "Enter001",
                             [(35.0, CUT_HEIGHT), (40.0, CUT_HEIGHT)],
                             lead=True, rapid=enter_rapid),
                add_movement(doc, "Path", "Path001",
                             [(40.0, CUT_HEIGHT), (50.0, CUT_HEIGHT)]),
                add_movement(doc, "Exit", "Exit002",
                             [(50.0, CUT_HEIGHT), (55.0, CUT_HEIGHT)],
                             lead=True, rapid=exit_rapid),
            ]
            route, blocks = self._route(doc, job, objects)

            enters = [b for b in blocks if b.obj_type == "Enter"]
            self.assertEqual(len(enters), 2,
                             "%s: expected two Enter blocks" % label)
            self.assertTrue(enters[1].moves,
                            "%s: second Enter block has no motion commands" % label)
            first = enters[1].moves[0]
            self.assertGreaterEqual(
                first.dest[1], SAFE_HEIGHT - EPS,
                "%s: Exit->Enter travel should start at safe height, got %s" %
                (label, first.dest))
            self.assertEqual(
                first.command, "G00",
                "%s: Exit->Enter travel at safe height must be rapid, got %s" %
                (label, first.command))
        finally:
            App.closeDocument(doc.Name)


class KerfDirectionTests(unittest.TestCase):
    '''Per-object kerf direction applies to Path and Projection geometry.'''

    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def offset_for(self, obj_type, direction):
        obj = add_movement(self.doc, obj_type, obj_type, [(10.0, 2.0), (20.0, 2.0)])
        route = build_route(self.doc, self.job, [obj], kerf = 1.0, strategy = "Uniform")
        obj.CompensationDirection = direction
        route.touch()
        route.recompute()
        return [(round(p.y, 3), round(p.z, 3)) for p in route.Offset_L]

    def test_path_and_projection_kerf_direction(self):
        for obj_type in ("Path", "Projection"):
            with self.subTest(obj_type = obj_type):
                self.assertEqual(self.offset_for(obj_type, "Normal"),
                                 [(10.0, 3.0), (20.0, 3.0)])
                self.assertEqual(self.offset_for(obj_type, "Reversed"),
                                 [(10.0, 1.0), (20.0, 1.0)])
                self.assertEqual(self.offset_for(obj_type, "None"),
                                 [(10.0, 2.0), (20.0, 2.0)])


# FreeCADCmd imports the passed script as a module (__name__ is the module
# basename, never "__main__"), so also run when this file is the entry script.
if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
