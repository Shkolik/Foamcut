# -*- coding: utf-8 -*-
"""G93 inverse-time feed rate mode tests. Run via FreeCADCmd.exe tests/test_g93.py"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import utilities
import Postprocess
import MachineConfig


def make_config(feed_rate_mode):
    cfg = type("Config", (), {})()
    cfg.CommentStyle = utilities.FC_COMMENT_STYLES[0]
    cfg.X1AxisName = "X"; cfg.Z1AxisName = "Y"; cfg.X2AxisName = "Z"; cfg.Z2AxisName = "A"; cfg.R1AxisName = "B"
    cfg.OriginX = 0
    cfg.FiveAxisMachine = True
    cfg.FeedRateMove = 30; cfg.FeedRateCut = 7; cfg.FeedRateRotate = 30
    cfg.FeedRateMode = feed_rate_mode
    cfg.EnableHoming = False; cfg.HomingCommand = "$H"
    cfg.HomingX1 = 110; cfg.HomingZ1 = 290; cfg.HomingX2 = 110; cfg.HomingZ2 = 290; cfg.HomingR1 = 0
    cfg.InitPositionCommand = "G92 {Position}"
    cfg.EnableParking = False; cfg.ParkX = 110; cfg.ParkZ = 290; cfg.ParkR1 = 0
    cfg.StartProgramCode = ""; cfg.EndProgramCode = ""
    cfg.MoveCommand = "G00 {Position} F{FeedRate}"
    cfg.CutCommand = "G01 {Position} F{FeedRate} {WirePower}"
    cfg.PauseCommand = "G04 P{Duration}"
    cfg.WireOnCommand = "M03 S{WirePower}"; cfg.WireOffCommand = "M05"
    cfg.WireMinPower = 700; cfg.WireMaxPower = 1000; cfg.DynamicWirePower = False
    cfg.FieldWidth = 730; cfg.HorizontalTravel = 550; cfg.VerticalTravel = 300
    cfg.BlockWidth = 400; cfg.BlockLength = 300; cfg.BlockHeight = 50
    cfg.BlockPosition = FreeCAD.Vector(-200, 275, 50)
    cfg.TimeUnits = utilities.FC_TIME_UNITS[0]
    return cfg


def make_route():
    obj = type("Object", (), {})()
    obj.Type = "Projection"; obj.Label = "Projection001"
    obj.PointsCount = 2; obj.FeedRate = 7; obj.WirePower = 700
    obj.RapidMove = False; obj.AddPause = False; obj.PauseDuration = 0
    route = type("Route", (), {})()
    route.Label = "Route001"
    route.Offset_L = [FreeCAD.Vector(0, 20, 120), FreeCAD.Vector(0, 30, 10.6)]
    route.Offset_R = [FreeCAD.Vector(0, 20, 120), FreeCAD.Vector(0, 30, 10.6)]
    route.Data = [0]
    route.Objects = [obj]
    route.FeedOverrides = [1.0]
    return route


def generate(cfg, routes, outpath):
    class FakeDialog:
        @staticmethod
        def getSaveFileName(*a, **k):
            return (outpath, "")
        def directory(self):
            return self
        def absolutePath(self):
            return ""
    Postprocess.QtGui.QFileDialog = FakeDialog
    pp = Postprocess.Postprocess()
    pp.makeGCODE(routes, cfg)
    with open(outpath) as f:
        return f.read()


class TestHarness(unittest.TestCase):
    def test_modules_import_and_constants_exist(self):
        self.assertEqual(utilities.FC_FEED_RATE_MODES, ["G94", "G93"])
        self.assertTrue(hasattr(Postprocess, "Postprocess"))
        self.assertIsInstance(Postprocess.Postprocess(), Postprocess.Postprocess)

    def test_generate_writes_program_file(self):
        import tempfile
        cfg = make_config(utilities.FC_FEED_RATE_MODES[0])
        outpath = os.path.join(tempfile.gettempdir(), "g93_harness.gcode")
        content = generate(cfg, [make_route()], outpath)
        self.assertIn("; *** START BLOCK ***", content)
        self.assertIn("G21", content)


class TestMachineConfig(unittest.TestCase):
    def test_new_config_defaults_to_g93(self):
        doc = App.newDocument("T_New")
        cfg = doc.addObject("App::DocumentObjectGroupPython", "Config")
        MachineConfig.MachineConfig(cfg, "T")
        self.assertEqual(cfg.FeedRateMode, "G93")

    def test_migration_defaults_to_g94(self):
        doc = App.newDocument("T_Mig")
        old = doc.addObject("App::DocumentObjectGroupPython", "OldConfig")
        mc = MachineConfig.MachineConfig.__new__(MachineConfig.MachineConfig)
        mc.onDocumentRestored(old)
        self.assertEqual(old.FeedRateMode, "G94")


G94_NO_PARK_EXPECTED = (
    "; *** MACHINE ***\n; Machine type: 5-Axis\n; Width: 730\n; Length: 550\n; Height: 300\n\n"
    "; *** FOAM BLOCK ***\n; Width: 400\n; Length: 300\n; Height: 50\n"
    "; Position - Left-Bottom-Front corner in relation to the origin\n"
    "; Position.X: -200.0\n; Position.Y: 275.0\n; Position.Z: 50.0\n\n"
    "; *** START BLOCK ***\n; Set units to millimeters\nG21\n; Set absolute positioning\nG90\n"
    "; Set G94 feed rate mode\nG94\nM03 S700.00\n\n"
    "; *** TASK BLOCK ***\n\n; --- Route begin [Route001] ---\n"
    "G00 X20.00 Y120.00 Z20.00 A120.00 F1800.00\n\n"
    "; - Projection [Projection001]\n"
    "G01 X20.00 Y120.00 Z20.00 A120.00 F420.00 \n"
    "G01 X30.00 Y10.60 Z30.00 A10.60 F420.00 \n"
    "; --- Route end [Route001] ---\n\n\n; *** END BLOCK ***\nM05\n"
)


class TestG94Mode(unittest.TestCase):
    def test_g94_no_parking_output_byte_identical_plus_g94_line(self):
        import tempfile
        cfg = make_config(utilities.FC_FEED_RATE_MODES[0])
        outpath = os.path.join(tempfile.gettempdir(), "g93_g94_nopark.gcode")
        content = generate(cfg, [make_route()], outpath)
        self.assertEqual(content, G94_NO_PARK_EXPECTED)


# FreeCADCmd imports the passed script as a module (__name__ is the module
# basename, never "__main__"), so also run when this file is the entry script.
if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)