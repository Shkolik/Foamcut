# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Describe machine configuration."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import utilities

class Config:
    def __init__(self, obj):
        obj.addProperty("App::PropertyLink",    "Volume", "", "", 5).Volume = FreeCAD.ActiveDocument.addObject("Part::Box", "CNCVolume")
        obj.addProperty("App::PropertyLink",    "WPL", "", "", 5).WPL = FreeCAD.ActiveDocument.addObject("Part::Plane", "WPL")
        obj.addProperty("App::PropertyLink",    "WPR", "", "", 5).WPR = FreeCAD.ActiveDocument.addObject("Part::Plane", "WPR")
        obj.addProperty("App::PropertyLink",    "RotationAxis", "", "", 5).RotationAxis = FreeCAD.ActiveDocument.addObject("Part::Line","RotationAxis")

        obj.addProperty("App::PropertyLength",     "HorizontalTravel", "Machine Geometry",  "Horizontal travel distance").HorizontalTravel = 800
        obj.addProperty("App::PropertyLength",     "VerticalTravel",   "Machine Geometry",  "Vertical travel distance"  ).VerticalTravel = 300   # - Vertical travel
        obj.addProperty("App::PropertyLength",     "FieldWidth",       "Machine Geometry",  "Distance between wire ends").FieldWidth = 500   # - Width
        
        obj.addProperty("App::PropertyString",     "X1AxisName",        "Axis Mapping",     "Name of X1 axis in GCODE").X1AxisName = "X"
        obj.addProperty("App::PropertyString",     "Z1AxisName",        "Axis Mapping",     "Name of Z1 axis in GCODE").Z1AxisName = "Y"
        obj.addProperty("App::PropertyString",     "X2AxisName",        "Axis Mapping",     "Name of X2 axis in GCODE").X2AxisName = "Z"
        obj.addProperty("App::PropertyString",     "Z2AxisName",        "Axis Mapping",     "Name of Z2 axis in GCODE").Z2AxisName = "A"
        obj.addProperty("App::PropertyString",     "R1AxisName",        "Axis Mapping",     "Name of rotary table axis in GCODE").R1AxisName = "B"


        obj.addProperty("App::PropertyDistance",    "HomingX1",         "Homing",           "Initial position for X1 axis").HomingX1 = 10
        obj.addProperty("App::PropertyDistance",    "HomingZ1",         "Homing",           "Initial position for Z1 axis").HomingZ1 = 290
        obj.addProperty("App::PropertyDistance",    "HomingX2",         "Homing",           "Initial position for X2 axis").HomingX2 = 10
        obj.addProperty("App::PropertyDistance",    "HomingZ2",         "Homing",           "Initial position for Z2 axis").HomingZ2 = 290
        obj.addProperty("App::PropertyDistance",    "HomingR1",         "Homing",           "Initial position for R1 axis").HomingR1 = 0

        obj.addProperty("App::PropertyDistance",    "ParkX",            "Parking",          "Parking position for X").ParkX = 10
        obj.addProperty("App::PropertyDistance",    "ParkZ",            "Parking",          "Parking position for Z").ParkZ = 290
        obj.addProperty("App::PropertyDistance",    "ParkR1",           "Parking",          "Parking position for rotary table").ParkR1 = 0

        obj.addProperty("App::PropertySpeed",      "FeedRateCut",       "FeedRate",         "Feed rate while cutting").FeedRateCut = 7
        obj.addProperty("App::PropertySpeed",      "FeedRateMove",      "FeedRate",         "Feed rate while moving").FeedRateMove = 14
        obj.addProperty("App::PropertySpeed",      "FeedRateRotate",    "FeedRate",         "Feed rate while rotating").FeedRateRotate = 30

        obj.addProperty("App::PropertyInteger",    "WireMinPower",      "Wire",             "Minimal wire power").WireMinPower = 500
        obj.addProperty("App::PropertyInteger",    "WireMaxPower",      "Wire",             "Maximal wire power").WireMaxPower = 1000

        obj.addProperty("App::PropertyString",     "CutCommand",           "GCODE",         "Command for move while cutting").CutCommand = "G01 {Position} F{FeedRate}"
        obj.addProperty("App::PropertyString",     "MoveCommand",          "GCODE",         "Command for move with cold wire").MoveCommand = "G00 {Position} F{FeedRate}"
        obj.addProperty("App::PropertyString",     "WireOnCommand",        "GCODE",         "Command for enable wire").WireOnCommand = "M03 S{WirePower}"
        obj.addProperty("App::PropertyString",     "WireOffCommand",       "GCODE",         "Command for disable wire").WireOffCommand = "M05"
        obj.addProperty("App::PropertyString",     "HomingCommand",        "GCODE",         "Command for homing procedure").HomingCommand = "$H"
        obj.addProperty("App::PropertyString",     "InitPositionCommand",  "GCODE",         "Command for initialize position").InitPositionCommand = "G92 {Position}"

        obj.addProperty("App::PropertyDistance",   "SafeHeight",           "Travel",        "Safe height for travel").SafeHeight = 200
        obj.addProperty("App::PropertyDistance",   "OriginX",              "Travel",        "Origin along X axis").OriginX = 0
        obj.addProperty("App::PropertyDistance",   "OriginY",              "Travel",        "Origin along Y axis").OriginY = obj.FieldWidth / 2

        obj.addProperty("App::PropertyDistance",   "OriginRotationX",      "Travel",        "Origin of rotation along X axis").OriginRotationX = obj.HorizontalTravel / 2
        obj.addProperty("App::PropertyDistance",   "OriginRotationY",      "Travel",        "Origin of rotationalong Y axis").OriginRotationY = obj.OriginY - obj.FieldWidth / 2


        obj.setEditorMode("Placement", 3)
        obj.setEditorMode("Label",     3)
        obj.Proxy = self

        obj.WPL.Support          = None
        obj.WPL.MapMode          = 'Deactivated'
        obj.WPL.MapPathParameter = 0.000000
        obj.WPL.MapReversed      = False
        obj.WPL.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))
        obj.WPL.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),90))
        obj.WPL.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,1,0),90)).multiply(obj.WPL.Placement)
        obj.WPL.ViewObject.LineColor = (1.0, 0.886, 0.023)
        obj.WPL.ViewObject.ShapeColor = (1.0, 0.886, 0.023)
        obj.WPL.ViewObject.LineWidth = 0

        obj.WPR.Support          = None
        obj.WPR.MapMode          = 'Deactivated'
        obj.WPR.MapPathParameter = 0.000000
        obj.WPR.MapReversed      = False
        obj.WPR.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))        
        obj.WPR.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),90))
        obj.WPR.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,1,0),90)).multiply(obj.WPR.Placement)
        obj.WPR.ViewObject.LineColor = (1.0, 0.886, 0.023)
        obj.WPR.ViewObject.ShapeColor = (1.0, 0.886, 0.023)
        obj.WPR.ViewObject.LineWidth = 0

        self.execute(obj)

    def onChanged(self, fp, prop):
        pass

    def execute(self, obj):
        print("recalculating config")
        # - Bounding box
        boundary = obj.Volume
        boundary.setEditorMode("Placement",     3)
        boundary.setEditorMode("Label",         3)
        boundary.setEditorMode("Width",         3)
        boundary.setEditorMode("Height",        3)
        boundary.setEditorMode("Length",        3)
        boundary.setEditorMode("AttachmentSupport",       3)
        boundary.setEditorMode("MapMode",       3)

        boundary.Placement.Base.y = obj.OriginX
        boundary.Placement.Base.x = obj.OriginY - obj.FieldWidth
        boundary.Length = obj.FieldWidth
        boundary.Width = obj.HorizontalTravel
        boundary.Height = obj.VerticalTravel
        boundary.ViewObject.Transparency = 90
        utilities.setPickStyle(boundary.ViewObject, utilities.UNPICKABLE)
        
        print("volume updated")

        # - Left working plane
        wpl = obj.WPL
        
        wpl.Width = obj.VerticalTravel
        wpl.Length = obj.HorizontalTravel
        wpl.Placement.Base.x = - obj.FieldWidth / 2
        wpl.Placement.Base.z = 0
        wpl.ViewObject.Transparency = 70
        print("WPL updated")

        # - Right working plane
        wpr = obj.WPR
        
        wpr.Width = obj.VerticalTravel
        wpr.Length = obj.HorizontalTravel
        wpr.Placement.Base.x = obj.FieldWidth / 2
        wpr.Placement.Base.z = 0
        wpr.ViewObject.Transparency = 70
        print("WPR updated")

        # - Rotation axis
        r1 = obj.RotationAxis
        r1.X1 = obj.OriginRotationY
        r1.Y1 = obj.OriginRotationX
        r1.Z1 = 0
        r1.X2= obj.OriginRotationY
        r1.Y2 = obj.OriginRotationX
        r1.Z2 = obj.VerticalTravel + 50
        r1.Placement = App.Placement(App.Vector(0.00,0.00,0.00),App.Rotation(App.Vector(0.00,0.00,1.00),0.00))
        r1.ViewObject.PointSize = 0
        r1.ViewObject.Transparency = 70
        r1.ViewObject.LineColor = (1.0, 0.886, 0.023)
        print("R1 updated")  

        # obj.recompute()

class ConfigVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("config.svg")
    
    if utilities.isNewStateHandling(): # - currently supported only in main branch FreeCad v0.21.2 and up
        def dumps(self):
            return {"name": self.Object.Name}

        def loads(self, state):
            self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
            return None

    else:
        def __getstate__(self):
            return {"name": self.Object.Name}

        def __setstate__(self, state):
            self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
            return None
        
    def claimChildren(self):
        return [self.Object.Volume, self.Object.WPL, self.Object.WPR, self.Object.RotationAxis]

def createConfig(obj):
    Config(obj)
    ConfigVP(obj.ViewObject)