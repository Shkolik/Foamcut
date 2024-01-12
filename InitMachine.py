# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Move path from selected point."
__usage__ = """Select start point on left or right plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import utilities

class Machine:
    def __init__(self, obj):
        obj.Proxy = self

    def onChanged(self, fp, prop):
        pass

    def execute(self, obj):
        pass

    def __getstate__(self):
        pass #return {"name": self.Object.Name}

    def __setstate__(self, state):
        pass #self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
        return None

class MachineVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        pass

    def getIcon(self):
        return utilities.getIconPath("machine.svg")
  
class InitMachine():
    """Init machine"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("foamcut.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Init machine",
                "ToolTip" : "Create Machine object and define working area and machine properties"}

    def Activated(self):
        # - Get document object
        doc = FreeCAD.activeDocument()
        # - Create bounding box
        boundary = doc.addObject("Part::Box", "CNCVolume")
        boundary.setEditorMode("Placement",     3)
        boundary.setEditorMode("Label",         3)
        boundary.setEditorMode("Width",         3)
        boundary.setEditorMode("Height",        3)
        boundary.setEditorMode("Length",        3)
        boundary.setEditorMode("Support",       3)
        boundary.setEditorMode("MapMode",       3)

        # - Create CNC configuration
        config = doc.addObject("Part::Feature", "Config")
        config.setEditorMode("Placement", 3)
        config.setEditorMode("Label",     3)
        config.addProperty("App::PropertyLength",     "HorizontalTravel", "Machine Geometry", "Horizontal travel distance")   # - Horizontal travel
        config.addProperty("App::PropertyLength",     "VerticalTravel",   "Machine Geometry", "Vertical travel distance"  )   # - Vertical travel
        config.addProperty("App::PropertyLength",     "FieldWidth",       "Machine Geometry", "Distance between wire ends")   # - Width

        config.addProperty("App::PropertyString",     "X1AxisName",    "Axis Mapping",     "Name of X1 axis in GCODE"     )
        config.addProperty("App::PropertyString",     "Z1AxisName",    "Axis Mapping",     "Name of Z1 axis in GCODE"     )

        config.addProperty("App::PropertyString",     "X2AxisName",    "Axis Mapping",     "Name of X2 axis in GCODE"     )
        config.addProperty("App::PropertyString",     "Z2AxisName",    "Axis Mapping",     "Name of Z2 axis in GCODE"     )

        config.addProperty("App::PropertyString",     "R1AxisName",    "Axis Mapping",     "Name of rotary table axis in GCODE")


        config.addProperty("App::PropertyDistance",     "HomingX1",      "Homing", "Initial position for X1 axis")
        config.addProperty("App::PropertyDistance",     "HomingZ1",      "Homing", "Initial position for Z1 axis")
        config.addProperty("App::PropertyDistance",     "HomingX2",      "Homing", "Initial position for X2 axis")
        config.addProperty("App::PropertyDistance",     "HomingZ2",      "Homing", "Initial position for Z2 axis")
        config.addProperty("App::PropertyDistance",     "HomingR1",      "Homing", "Initial position for R1 axis")

        config.addProperty("App::PropertyDistance",      "ParkX",         "Parking", "Parking position for X")
        config.addProperty("App::PropertyDistance",      "ParkZ",         "Parking", "Parking position for Z")
        config.addProperty("App::PropertyDistance",      "ParkR1",        "Parking", "Parking position for rotary table")

        config.addProperty("App::PropertySpeed",      "FeedRateCut",     "FeedRate",   "Feed rate while cutting")
        config.addProperty("App::PropertySpeed",      "FeedRateMove",    "FeedRate",   "Feed rate while moving")
        config.addProperty("App::PropertySpeed",      "FeedRateRotate",  "FeedRate",   "Feed rate while rotating")

        config.addProperty("App::PropertyInteger",    "WireMinPower",     "Wire",         "Minimal wire power")
        config.addProperty("App::PropertyInteger",    "WireMaxPower",     "Wire",         "Maximal wire power")

        config.addProperty("App::PropertyString",     "CutCommand",           "GCODE",        "Command for move while cutting")
        config.addProperty("App::PropertyString",     "MoveCommand",          "GCODE",        "Command for move")
        config.addProperty("App::PropertyString",     "WireOnCommand",        "GCODE",        "Command for enable wire")
        config.addProperty("App::PropertyString",     "WireOffCommand",       "GCODE",        "Command for disable wire")
        config.addProperty("App::PropertyString",     "HomingCommand",        "GCODE",        "Command for homing procedure")
        config.addProperty("App::PropertyString",     "InitPositionCommand",  "GCODE",        "Command for initialize position")

        config.addProperty("App::PropertyDistance",   "SafeHeight",           "Travel",       "Safe height for travel")

        # - Set boundary
        config.HorizontalTravel = 490
        config.VerticalTravel   = 235
        config.FieldWidth       = 374

        # - Set axis mapping
        config.X1AxisName  = "X"
        config.Z1AxisName  = "Y"
        config.X2AxisName  = "Z"
        config.Z2AxisName  = "A"
        config.R1AxisName  = "B"

        # - Set default homing positions
        config.HomingX1 = 249
        config.HomingZ1 = 238
        config.HomingX2 = 245
        config.HomingZ2 = 236
        config.HomingR1 = -7.3

        config.FeedRateCut      = 7
        config.FeedRateMove     = 14
        config.FeedRateRotate   = 30
        config.WireMinPower     = 500
        config.WireMaxPower     = 1000

        config.CutCommand           = "G01 {Position} F{FeedRate}"
        config.MoveCommand          = "G00 {Position} F{FeedRate}"
        config.HomingCommand        = "$H"
        config.WireOnCommand        = "M03 S{WirePower}"
        config.WireOffCommand       = "M05"
        config.InitPositionCommand  = "G92 {Position}"

        config.ParkX  = 240
        config.ParkZ  = 235
        config.ParkR1 = 0
        config.SafeHeight = 200

        # - Link boundary
        boundary.setExpression(".Placement.Base.y", u"-<<Config>>.HorizontalTravel / 2")
        boundary.setExpression(".Placement.Base.x", u"-<<Config>>.FieldWidth / 2")
        boundary.setExpression(".Length",           u"<<Config>>.FieldWidth")
        boundary.setExpression(".Width",            u"<<Config>>.HorizontalTravel")
        boundary.setExpression(".Height",           u"<<Config>>.VerticalTravel")
        boundary.ViewObject.Transparency = 90
        boundary.recompute()

        # - Create CNC support
        cnc = doc.addObject("PartDesign::Body", "CNC")
        cnc.setEditorMode("Placement",    3)
        cnc.setEditorMode("Label",        3)
        cnc.setEditorMode("Tip",          3)
        cnc.setEditorMode("BaseFeature",  3)
        cnc.setEditorMode("Group",        3)

        # - Create working plane #L
        wp = cnc.newObject("PartDesign::Plane", "WPL")
        wp.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))
        wp.Support          = None
        wp.MapMode          = 'Deactivated'
        wp.MapPathParameter = 0.000000
        wp.MapReversed      = False
        wp.ResizeMode       = 'Manual'
        wp.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(1,0,0),90)).multiply(wp.Placement)
        wp.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),-90)).multiply(wp.Placement)
        wp.setExpression(".Width",   u"<<Config>>.VerticalTravel")
        wp.setExpression(".Length",    u"<<Config>>.HorizontalTravel")
        wp.setExpression(".Placement.Base.x", u"-<<Config>>.FieldWidth / 2")
        wp.setExpression(".Placement.Base.z", u"<<Config>>.VerticalTravel / 2")
        wp.recompute()

        # - Create working plane #R
        wp = cnc.newObject("PartDesign::Plane", "WPR")
        wp.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))
        wp.Support          = None
        wp.MapMode          = 'Deactivated'
        wp.MapPathParameter = 0.000000
        wp.MapReversed      = False
        wp.ResizeMode       = 'Manual'
        wp.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(1,0,0),90)).multiply(wp.Placement)
        wp.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),90)).multiply(wp.Placement)
        wp.setExpression(".Width",   u"<<Config>>.VerticalTravel")
        wp.setExpression(".Length",    u"<<Config>>.HorizontalTravel")
        wp.setExpression(".Placement.Base.x", u"<<Config>>.FieldWidth / 2")
        wp.setExpression(".Placement.Base.z", u"<<Config>>.VerticalTravel / 2")
        wp.recompute()

        # - Create group
        machine = doc.addObject("App::DocumentObjectGroupPython", "Machine")
        Machine(machine)
        MachineVP(machine.ViewObject)

        machine.Group = [config, cnc, boundary]

        machine.recompute()
        return

    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            setup = App.ActiveDocument.getObject("Machine")
            if setup:
                return False
        return True

Gui.addCommand("InitMachine", InitMachine())