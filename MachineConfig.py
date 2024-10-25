# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Describe machine configuration."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutBase
import FoamCutViewProviders
import RotationAxis
import utilities


class MachineConfig(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):
        super().__init__(obj, jobName)     
        obj.Type = "Helper"  
        
        obj.addProperty("App::PropertyBool",       "FiveAxisMachine",  "Machine Geometry",  "Enable rotation axis if it's 5 axis machine").FiveAxisMachine = getParameterBool("FiveAxisMachine", True)
        obj.addProperty("App::PropertyLength",     "HorizontalTravel", "Machine Geometry",  "Horizontal travel distance").HorizontalTravel = getParameterFloat("HorizontalTravel", 550)
        obj.addProperty("App::PropertyLength",     "VerticalTravel",   "Machine Geometry",  "Vertical travel distance"  ).VerticalTravel = getParameterFloat("VerticalTravel", 300)
        obj.addProperty("App::PropertyLength",     "FieldWidth",       "Machine Geometry",  "Distance between wire ends").FieldWidth = getParameterFloat("FieldWidth", 730)
        obj.addProperty("App::PropertyDistance",   "OriginX",          "Machine Geometry",  "Origin along X axis").OriginX = getParameterFloat("OriginX", 0)
        obj.addProperty("App::PropertyDistance",   "OriginRotationX",  "Machine Geometry",  "Position of rotation axis along X axis").OriginRotationX = obj.HorizontalTravel / 2
        
        obj.addProperty("App::PropertyString",     "X1AxisName",        "Axis Mapping",     "Name of X1 axis in GCODE").X1AxisName = getParameterString("X1AxisName", "X")
        obj.addProperty("App::PropertyString",     "Z1AxisName",        "Axis Mapping",     "Name of Z1 axis in GCODE").Z1AxisName = getParameterString("Z1AxisName","Y")
        obj.addProperty("App::PropertyString",     "X2AxisName",        "Axis Mapping",     "Name of X2 axis in GCODE").X2AxisName = getParameterString("X2AxisName", "Z")
        obj.addProperty("App::PropertyString",     "Z2AxisName",        "Axis Mapping",     "Name of Z2 axis in GCODE").Z2AxisName = getParameterString("Z2AxisName", "A")
        obj.addProperty("App::PropertyString",     "R1AxisName",        "Axis Mapping",     "Name of rotary table axis in GCODE").R1AxisName = getParameterString("R1AxisName", "B")

        obj.addProperty("App::PropertyBool",        "EnableHoming",     "Homing",           "Enable homing before cycle start").EnableHoming = getParameterBool("EnableHoming", False)
        obj.addProperty("App::PropertyDistance",    "HomingX1",         "Homing",           "Initial position for X1 axis").HomingX1 = getParameterFloat("HomingX1", 10)
        obj.addProperty("App::PropertyDistance",    "HomingZ1",         "Homing",           "Initial position for Z1 axis").HomingZ1 = getParameterFloat("HomingZ1", 290)
        obj.addProperty("App::PropertyDistance",    "HomingX2",         "Homing",           "Initial position for X2 axis").HomingX2 = getParameterFloat("HomingX2", 10)
        obj.addProperty("App::PropertyDistance",    "HomingZ2",         "Homing",           "Initial position for Z2 axis").HomingZ2 = getParameterFloat("HomingZ2", 290)
        obj.addProperty("App::PropertyDistance",    "HomingR1",         "Homing",           "Initial position for R1 axis").HomingR1 = getParameterFloat("HomingR1", 0)

        obj.addProperty("App::PropertyBool",        "EnableParking",    "Parking",          "Enable parking before cycle start and after cycle ends").EnableParking = getParameterBool("EnableParking", False)
        obj.addProperty("App::PropertyDistance",    "ParkX",            "Parking",          "Parking position for X").ParkX = getParameterFloat("ParkX", 10)
        obj.addProperty("App::PropertyDistance",    "ParkZ",            "Parking",          "Parking position for Z").ParkZ = getParameterFloat("ParkZ", 290)
        obj.addProperty("App::PropertyDistance",    "ParkR1",           "Parking",          "Parking position for rotary table").ParkR1 = getParameterFloat("ParkR1", 0)

        obj.addProperty("App::PropertySpeed",      "FeedRateCut",       "FeedRate",         "Feed rate while cutting").FeedRateCut = getParameterFloat("FeedRateCut", 7)
        obj.addProperty("App::PropertySpeed",      "FeedRateMove",      "FeedRate",         "Feed rate while moving").FeedRateMove = getParameterFloat("FeedRateMove", 30)
        obj.addProperty("App::PropertySpeed",      "FeedRateRotate",    "FeedRate",         "Feed rate while rotating").FeedRateRotate = getParameterFloat("FeedRateRotate", 30)

        obj.addProperty("App::PropertyInteger",    "WireMinPower",      "Wire",             "Minimum wire power").WireMinPower = getParameterInt("WireMinPower", 700)
        obj.addProperty("App::PropertyInteger",    "WireMaxPower",      "Wire",             "Maximum wire power").WireMaxPower = getParameterInt("WireMaxPower", 1000)
        obj.addProperty("App::PropertyBool",       "DynamicWirePower",  "Wire",             "Dynamic wire power. " + 
                        "Power will vary depending on wire length. When enabling be sure that your controller set to Laser mode, " + 
                        "otherwise machine will halt for a brif moment after each move.").DynamicWirePower = getParameterBool("DynamicWirePower", False)
        obj.addProperty("App::PropertyLength",     "KerfCompensation",      "Kerf Compensation",    "Kerf Compensation").KerfCompensation = getParameterFloat("KerfCompensation", 0.6)
        obj.addProperty("App::PropertyFloat",     "CompensationDegree",      "Kerf Compensation",    "Kerf Compensation coefficient. \r\n\
                        This coefficient help calculate kerf compensation when wire speed is less than nominal. \r\n\
                        Usually kerf thickness is directly related to movement speed. Lesser speed - thicker kerf. \
                        But in some foams it will not be that simple, since wire melts foam and it became dencer. \r\n\
                        Normally it should be 1.0, but for denser foam it could be bigger.").CompensationDegree = getParameterFloat("CompensationDegree", 1.0)
        
        obj.addProperty("App::PropertyLength",     "DiscretizationStep",   "GCODE",         "Discretization step").DiscretizationStep = 0.5
        obj.addProperty("App::PropertyString",     "CutCommand",           "GCODE",         "Command for move while cutting").CutCommand = getParameterString("CutCommand", "G01 {Position} F{FeedRate} {WirePower}")
        obj.addProperty("App::PropertyString",     "MoveCommand",          "GCODE",         "Command for move with cold wire").MoveCommand = getParameterString("MoveCommand", "G00 {Position} F{FeedRate}")
        obj.addProperty("App::PropertyString",     "PauseCommand",         "GCODE",         "Command for pause movements").PauseCommand = getParameterString("PauseCommand", "G04 P{Duration}")
        obj.addProperty("App::PropertyString",     "WireOnCommand",        "GCODE",         "Command for enable wire").WireOnCommand = getParameterString("WireOnCommand", "M03 S{WirePower}")
        obj.addProperty("App::PropertyString",     "WireOffCommand",       "GCODE",         "Command for disable wire").WireOffCommand = getParameterString("WireOffCommand", "M05")
        obj.addProperty("App::PropertyString",     "HomingCommand",        "GCODE",         "Command for homing procedure").HomingCommand = getParameterString("HomingCommand", "$H")
        obj.addProperty("App::PropertyString",     "InitPositionCommand",  "GCODE",         "Command for initialize position").InitPositionCommand = getParameterString("InitPositionCommand", "G92 {Position}")
        obj.addProperty("App::PropertyEnumeration","TimeUnits",            "GCODE",         "Units for time in Gcode. " + 
                        "GRBL usually use seconds, other controllers may use milliseconds").TimeUnits = utilities.FC_TIME_UNITS
        obj.TimeUnits = utilities.FC_TIME_UNITS.index(getParameterString("TimeUnits", "Seconds"))

        obj.addProperty("App::PropertyDistance",   "SafeHeight",           "Travel",        "Safe height for travel").SafeHeight = getParameterFloat("SafeHeight", 200)        
        obj.addProperty("App::PropertyTime",       "PauseDuration",        "Travel",        "Pause duration seconds").PauseDuration = getParameterFloat("PauseDuration", 1.0)
        
        obj.addProperty("App::PropertyLength",     "BlockWidth",            "Foam Block",   "Foam block size along wire").BlockWidth = getParameterFloat("BlockWidth", 400)
        obj.addProperty("App::PropertyLength",     "BlockLength",           "Foam Block",   "Foam block size along machine X axis").BlockLength = getParameterFloat("BlockLength", 300)
        obj.addProperty("App::PropertyLength",     "BlockHeight",           "Foam Block",   "Foam block size along machine Y axis").BlockHeight = getParameterFloat("BlockHeight", 50)
        obj.addProperty("App::PropertyPosition",   "BlockPosition",         "Foam Block",   "Foam block position in machine coordinates (x,y,z) where x - coordinate along wire, y - coordinate along machine X axis, z - coordinate along machine Y axis")
        obj.BlockPosition = App.Vector(float(-obj.BlockWidth / 2.0), float(obj.HorizontalTravel / 2.0) - float(obj.BlockLength / 2), getParameterFloat("BlockPositionHeight", 50) )

        obj.setEditorMode("HomingCommand", 0 if obj.EnableHoming else 3)     
        obj.setEditorMode("HomingX1", 0 if obj.EnableHoming else 3)
        obj.setEditorMode("HomingX2", 0 if obj.EnableHoming else 3)
        obj.setEditorMode("HomingZ1", 0 if obj.EnableHoming else 3)
        obj.setEditorMode("HomingZ2", 0 if obj.EnableHoming else 3)
        obj.setEditorMode("HomingR1", 0 if obj.EnableHoming and obj.FiveAxisMachine else 3)
        obj.setEditorMode("ParkX", 0 if obj.EnableParking else 3)
        obj.setEditorMode("ParkZ", 0 if obj.EnableParking else 3)
        obj.setEditorMode("ParkR1", 0 if obj.EnableParking and obj.FiveAxisMachine else 3)
        obj.setEditorMode("OriginRotationX", 0 if obj.FiveAxisMachine else 3)
        obj.setEditorMode("R1AxisName", 0 if obj.FiveAxisMachine else 3)

        obj.setEditorMode("Group",     3)
        obj.Proxy = self
        self.execute(obj)

    def onDocumentRestored(self, obj):
        # Migrating from 0.1.2 to 0.1.3 - this properties needed for dynamic kerf compensation
        if not hasattr(obj, "CompensationDegree"):
            obj.addProperty("App::PropertyFloat",     "CompensationDegree",      "Kerf Compensation",    "Kerf Compensation coefficient. \r\n\
                        This coefficient help calculate kerf compensation when wire speed is less than nominal. \r\n\
                        Usually kerf thickness is directly related to movement speed. Lesser speed - thicker kerf. \
                        But in some foams it will not be that simple, since wire melts foam and it became dencer. \r\n\
                        Normally it should be 1.0, but for denser foam it could be bigger.").CompensationDegree = getParameterFloat("CompensationDegree", 1.0)
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDegree property.".format(obj.Label))

        if hasattr(obj, "KerfCompensation") and obj.getGroupOfProperty("KerfCompensation") != "Kerf Compensation":
            obj.setGroupOfProperty("KerfCompensation", "Kerf Compensation")
        
        if hasattr(obj, "CompensationDegree"):
            print("{} - Migrating from 0.1.3 to 0.1.4 - hiding CompensationDegree property.".format(obj.Label))
            obj.setEditorMode("CompensationDegree", 2)

    def execute(self, obj):
        
        pass 
        
    def onChanged(self, obj, prop):
        if prop == "FiveAxisMachine":
            machine = App.ActiveDocument.getObject(obj.JobName)
            if machine is not None:
                axis = None
                for child in machine.Group:
                    if hasattr(child, "Type") and child.Type == "RotationAxis":
                        axis = child
                        break

                if axis is not None:
                    App.ActiveDocument.removeObject(axis.Name)

                if obj.FiveAxisMachine:
                    axis = machine.newObject("App::FeaturePython", "RotationAxis")    
                    axis.Label = "Rotation Axis"
                    RotationAxis.CreateRotationAxis(axis, machine.Name)
                    

            obj.setEditorMode("OriginRotationX", 0 if obj.FiveAxisMachine else 3)
            obj.setEditorMode("R1AxisName", 0 if obj.FiveAxisMachine else 3)
        if prop == "EnableParking":
            obj.setEditorMode("ParkX", 0 if obj.EnableParking else 3)
            obj.setEditorMode("ParkZ", 0 if obj.EnableParking else 3)
            obj.setEditorMode("ParkR1", 0 if obj.EnableParking and obj.FiveAxisMachine else 3)
        if prop == "EnableHoming":
            obj.setEditorMode("HomingCommand", 0 if obj.EnableHoming else 3)     
            obj.setEditorMode("HomingX1", 0 if obj.EnableHoming else 3)
            obj.setEditorMode("HomingX2", 0 if obj.EnableHoming else 3)
            obj.setEditorMode("HomingZ1", 0 if obj.EnableHoming else 3)
            obj.setEditorMode("HomingZ2", 0 if obj.EnableHoming else 3)
            obj.setEditorMode("HomingR1", 0 if obj.EnableHoming and obj.FiveAxisMachine else 3) 
                  
        pass

class MachineConfigVP(FoamCutViewProviders.FoamCutBaseViewProvider):    
    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        obj.Visibility = True

    def getIcon(self):
        return utilities.getIconPath("config.svg")
    
def getParameterFloat(name, default):
    parameters = App.ParamGet("User parameter:BaseApp/Workbench/FoamcutWB/DefaultMachineConfig")
    floats = parameters.GetFloats()
    if name not in floats:
        parameters.SetFloat(name, default)
    
    return parameters.GetFloat(name)

def getParameterInt(name, default):
    parameters = App.ParamGet("User parameter:BaseApp/Workbench/FoamcutWB/DefaultMachineConfig")
    ints = parameters.GetInts()
    if name not in ints:
        parameters.SetInt(name, default)
    
    return parameters.GetInt(name)

def getParameterBool(name, default):
    parameters = App.ParamGet("User parameter:BaseApp/Workbench/FoamcutWB/DefaultMachineConfig")
    bools = parameters.GetBools()
    if name not in bools:
        parameters.SetBool(name, default)
    
    return parameters.GetBool(name)

def getParameterString(name, default):
    parameters = App.ParamGet("User parameter:BaseApp/Workbench/FoamcutWB/DefaultMachineConfig")
    strings = parameters.GetStrings()
    if name not in strings:
        parameters.SetString(name, default)
    
    return parameters.GetString(name)

def createConfig(obj, jobName):
    MachineConfig(obj, jobName)
    MachineConfigVP(obj.ViewObject)