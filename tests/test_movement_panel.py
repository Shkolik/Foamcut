# -*- coding: utf-8 -*-
"""Movement task panel machinery tests. Run via FreeCADCmd.exe tests/test_movement_panel.py"""

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

import FoamCutBase
import utilities
from test_route_postprocess import add_movement, build_route, new_document


class TestExpressionHelpers(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("ExprPanel")
        self.config = self.doc.addObject("App::FeaturePython", "Config")
        self.config.addProperty("App::PropertySpeed", "FeedRateCut", "", "")
        self.config.FeedRateCut = 7.0

        self.obj = self.doc.addObject("App::FeaturePython", "Obj")
        self.obj.addProperty("App::PropertySpeed", "FeedRate", "", "")
        self.obj.setExpression(".FeedRate", u"<<Config>>.FeedRateCut")
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_expression_is_detected(self):
        self.assertTrue(utilities.hasPropertyExpression(self.obj, "FeedRate"))
        self.assertEqual(utilities.getPropertyExpression(self.obj, "FeedRate"), u"<<Config>>.FeedRateCut")
        self.assertFalse(utilities.hasPropertyExpression(self.obj, "Other"))

    def test_override_detaches_expression(self):
        utilities.overrideProperty(self.obj, "FeedRate", 12.5)
        self.assertFalse(utilities.hasPropertyExpression(self.obj, "FeedRate"))
        self.assertAlmostEqual(float(self.obj.FeedRate), 12.5)

    def test_restore_expression_rebinds_value(self):
        utilities.overrideProperty(self.obj, "FeedRate", 12.5)
        utilities.restorePropertyExpression(self.obj, "FeedRate", u"<<Config>>.FeedRateCut")
        self.doc.recompute()
        self.assertTrue(utilities.hasPropertyExpression(self.obj, "FeedRate"))
        self.assertAlmostEqual(float(self.obj.FeedRate), 7.0)

    def test_clear_expression_keeps_value(self):
        utilities.clearPropertyExpression(self.obj, "FeedRate")
        self.assertFalse(utilities.hasPropertyExpression(self.obj, "FeedRate"))
        self.assertAlmostEqual(float(self.obj.FeedRate), 7.0)

    def test_preferred_value_round_trips(self):
        quantity = FreeCAD.Units.Quantity(2.75, FreeCAD.Units.Velocity)
        display, unit, factor = utilities.getPreferredValue(quantity)
        self.assertTrue(unit)
        self.assertAlmostEqual(display * factor, 2.75)


class TestRouteLookup(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_document()
        objects = [
            add_movement(self.doc, "Enter", "Enter", [(5.0, 2.0), (10.0, 2.0)], lead=True),
            add_movement(self.doc, "Path", "Path", [(10.0, 2.0), (20.0, 2.0)]),
            add_movement(self.doc, "Exit", "Exit", [(20.0, 2.0), (25.0, 2.0)], lead=True),
        ]
        self.route = build_route(self.doc, self.job, objects)
        self.path = objects[1]

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_routes_using_object(self):
        self.assertEqual(FoamCutBase.getRoutesForObject(self.path), [self.route])

    def test_unused_object_has_no_routes(self):
        outside = add_movement(self.doc, "Path", "Outside", [(30.0, 2.0), (40.0, 2.0)])
        self.assertEqual(FoamCutBase.getRoutesForObject(outside), [])

    def test_recompute_routes(self):
        expected = list(self.route.Offset_L)
        self.route.Offset_L = []
        FoamCutBase.recomputeRoutesForObject(self.path)
        self.assertEqual(list(self.route.Offset_L), expected)


class TestMovementGuiSurface(unittest.TestCase):
    def test_gui_module_exposes_panel_machinery(self):
        import MovementGui
        self.assertTrue(hasattr(MovementGui, "MovementTaskPanel"))
        self.assertTrue(hasattr(MovementGui, "MoveTaskPanel"))
        self.assertTrue(hasattr(MovementGui, "showMovementPanel"))
        self.assertTrue(hasattr(MovementGui, "openMovementPanel"))
        self.assertEqual(sorted(MovementGui.PANELS.keys()),
                         ["Enter", "Exit", "Join", "Move", "Path", "Projection"])

    def test_object_panels_are_available(self):
        import TaskPanelBase
        import RotationGui
        import RouteGui
        import MoveGui
        import EnterGui
        import ExitGui
        import JoinGui
        import PathGui
        import ProjectionGui
        self.assertTrue(hasattr(TaskPanelBase, "BaseTaskPanel"))
        self.assertTrue(hasattr(RotationGui, "RotationTaskPanel"))
        self.assertTrue(hasattr(RouteGui, "RouteTaskPanel"))
        self.assertTrue(hasattr(MoveGui, "MakeMove"))
        self.assertTrue(hasattr(EnterGui, "MakeEnter"))
        self.assertTrue(hasattr(ExitGui, "MakeExit"))
        self.assertTrue(hasattr(JoinGui, "MakeJoin"))
        self.assertTrue(hasattr(PathGui, "MakePath"))
        self.assertTrue(hasattr(ProjectionGui, "MakeProjection"))

    def test_legacy_view_provider_aliases(self):
        import WireMove
        import WireEnter
        import WireExit
        import WireJoin
        import WirePath
        import WireProjection
        import Rotate
        import WireRoute
        import MoveGui
        import EnterGui
        import ExitGui
        import JoinGui
        import PathGui
        import ProjectionGui
        import RotationGui
        import RouteGui

        self.assertIs(WireMove.WireMoveVP, MoveGui.WireMoveVP)
        self.assertIs(WireEnter.WireEnterVP, EnterGui.WireEnterVP)
        self.assertIs(WireExit.WireExitVP, ExitGui.WireExitVP)
        self.assertIs(WireJoin.WireJoinVP, JoinGui.WireJoinVP)
        self.assertIs(WirePath.PathSectionVP, PathGui.PathSectionVP)
        self.assertIs(WireProjection.ProjectionSectionVP, ProjectionGui.ProjectionSectionVP)
        self.assertIs(Rotate.RotationVP, RotationGui.RotationVP)
        self.assertIs(WireRoute.WireRouteVP, RouteGui.WireRouteVP)


class TestPanelProperties(unittest.TestCase):
    def test_feed_and_power_are_optional(self):
        import MovementGui

        class Dummy:
            Type = "Enter"
            CompensationDirection = "Normal"

        panel = MovementGui.MovementTaskPanel.__new__(MovementGui.MovementTaskPanel)
        panel.obj = Dummy()
        names = panel.properties()
        self.assertNotIn("FeedRate", names)
        self.assertNotIn("WirePower", names)
        self.assertIn("RapidMove", names)

        Dummy.FeedRate = 1.0
        Dummy.WirePower = 1
        names = panel.properties()
        self.assertIn("FeedRate", names)
        self.assertIn("WirePower", names)

    def test_path_and_projection_list_kerf_direction(self):
        import MovementGui

        class Dummy:
            Type = "Path"
            CompensationDirection = "Normal"

        panel = MovementGui.MovementTaskPanel.__new__(MovementGui.MovementTaskPanel)
        panel.obj = Dummy()

        self.assertTrue(panel.hasCompensationDirection())
        self.assertIn("CompensationDirection", panel.properties())

        Dummy.Type = "Projection"
        self.assertTrue(panel.hasCompensationDirection())
        self.assertIn("CompensationDirection", panel.properties())

    def test_standard_buttons_are_int(self):
        import TaskPanelBase
        buttons = TaskPanelBase.BaseTaskPanel.getStandardButtons(None)
        self.assertIsInstance(buttons, int)
        self.assertTrue(buttons)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
