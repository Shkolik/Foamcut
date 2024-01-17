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

class MachineConfig:
    def __init__(self, obj):
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

        obj.addProperty("App::PropertyDistance",   "OriginRotationX",      "Travel",        "Origin of rotation along X axis").OriginRotationX = obj.HorizontalTravel / 2

        obj.addProperty("App::PropertyLength",     "BlockWidth",            "Foam Block",   "Foam block size along wire").BlockWidth = 400
        obj.addProperty("App::PropertyLength",     "BlockLength",           "Foam Block",   "Foam block size along machine X axis").BlockLength = 300
        obj.addProperty("App::PropertyLength",     "BlockHeight",           "Foam Block",   "Foam block size along machine Y axis").BlockHeight = 50
        obj.addProperty("App::PropertyPosition",   "BlockPosition",         "Foam Block",   "Foam block position in machine coordinates (x,y,z) where x - coordinate along wire, y - coordinate along machine X axis, z - coordinate along machine Y axis").BlockPosition = App.Vector(-200.0, obj.HorizontalTravel / 2 - 150.0, 50.0 )

        obj.setEditorMode("Group",     3)
        obj.Proxy = self
        self.execute(obj)

    def onChanged(self, fp, prop):
        pass

    def execute(self, obj):
        pass 
        

class MachineConfigVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        obj.Visibility = True

    def doubleClicked(self, obj):
        return True
    
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
        
def createConfig(obj):
    MachineConfig(obj)
    MachineConfigVP(obj.ViewObject)