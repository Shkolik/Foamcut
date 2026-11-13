# -*- coding: utf-8 -*-

__title__ = "Job configuration properties"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Machine and process settings stored directly on the Job object."

import FreeCAD
App = FreeCAD
import utilities

RESERVED_PROPERTIES = {
    "Type",
    "JobName",
    "ConfigName",
    "WPLName",
    "WPRName",
    "Group",
    "Label",
    "Label2",
    "Proxy",
    "Visibility",
    "ExpressionEngine",
    "MigrationVersion",
}

_CONFIG_NAMES = []
CONFIG_PROPERTIES = set()


def applyConfigProperties(obj):
    '''
    Add machine/process properties to a Job object.
    Existing properties are left untouched, so this is safe for migration.
    '''
    def add(prop_type, name, group, description, value):
        if name not in _CONFIG_NAMES:
            _CONFIG_NAMES.append(name)
        CONFIG_PROPERTIES.add(name)
        if hasattr(obj, name):
            return False
        obj.addProperty(prop_type, name, group, description)
        setattr(obj, name, value)
        return True

    add("App::PropertyBool", "FiveAxisMachine", "Machine Geometry", "Enable rotation axis if it's 5 axis machine", utilities.getParameterBool("FiveAxisMachine", True))
    add("App::PropertyLength", "HorizontalTravel", "Machine Geometry", "Horizontal travel distance", utilities.getParameterFloat("HorizontalTravel", 870))
    add("App::PropertyLength", "VerticalTravel", "Machine Geometry", "Vertical travel distance", utilities.getParameterFloat("VerticalTravel", 330))
    add("App::PropertyLength", "FieldWidth", "Machine Geometry", "Distance between wire ends", utilities.getParameterFloat("FieldWidth", 740))
    add("App::PropertyDistance", "OriginX", "Machine Geometry", "Origin along X axis", utilities.getParameterFloat("OriginX", 0))
    add("App::PropertyDistance", "OriginRotationX", "Machine Geometry", "Position of rotation axis along X axis", obj.HorizontalTravel / 2)

    add("App::PropertyString", "X1AxisName", "Axis Mapping", "Name of X1 axis in GCODE", utilities.getParameterString("X1AxisName", "X"))
    add("App::PropertyString", "Z1AxisName", "Axis Mapping", "Name of Z1 axis in GCODE", utilities.getParameterString("Z1AxisName", "Y"))
    add("App::PropertyString", "X2AxisName", "Axis Mapping", "Name of X2 axis in GCODE", utilities.getParameterString("X2AxisName", "Z"))
    add("App::PropertyString", "Z2AxisName", "Axis Mapping", "Name of Z2 axis in GCODE", utilities.getParameterString("Z2AxisName", "A"))
    add("App::PropertyString", "R1AxisName", "Axis Mapping", "Name of rotary table axis in GCODE", utilities.getParameterString("R1AxisName", "B"))

    add("App::PropertyBool", "EnableHoming", "Homing", "Enable homing before cycle start", utilities.getParameterBool("EnableHoming", False))
    add("App::PropertyDistance", "HomingX1", "Homing", "Initial position for X1 axis", utilities.getParameterFloat("HomingX1", 868))
    add("App::PropertyDistance", "HomingZ1", "Homing", "Initial position for Z1 axis", utilities.getParameterFloat("HomingZ1", 328))
    add("App::PropertyDistance", "HomingX2", "Homing", "Initial position for X2 axis", utilities.getParameterFloat("HomingX2", 868))
    add("App::PropertyDistance", "HomingZ2", "Homing", "Initial position for Z2 axis", utilities.getParameterFloat("HomingZ2", 328))
    add("App::PropertyDistance", "HomingR1", "Homing", "Initial position for R1 axis", utilities.getParameterFloat("HomingR1", 0))

    add("App::PropertyBool", "EnableParking", "Parking", "Enable parking before cycle start and after cycle ends", utilities.getParameterBool("EnableParking", False))
    add("App::PropertyDistance", "ParkX", "Parking", "Parking position for X", utilities.getParameterFloat("ParkX", 110))
    add("App::PropertyDistance", "ParkZ", "Parking", "Parking position for Z", utilities.getParameterFloat("ParkZ", 200))
    add("App::PropertyDistance", "ParkR1", "Parking", "Parking position for rotary table", utilities.getParameterFloat("ParkR1", 0))

    add("App::PropertySpeed", "FeedRateCut", "FeedRate", "Feed rate while cutting", utilities.getParameterFloat("FeedRateCut", 2.66))
    add("App::PropertySpeed", "FeedRateMove", "FeedRate", "Feed rate while moving", utilities.getParameterFloat("FeedRateMove", 30))
    add("App::PropertySpeed", "FeedRateRotate", "FeedRate", "Feed rate while rotating", utilities.getParameterFloat("FeedRateRotate", 12))

    add("App::PropertyInteger", "WireMinPower", "Wire", "Minimum wire power", utilities.getParameterInt("WireMinPower", 860))
    add("App::PropertyInteger", "WireMaxPower", "Wire", "Maximum wire power", utilities.getParameterInt("WireMaxPower", 1000))
    add("App::PropertyBool", "DynamicWirePower", "Wire", "Dynamic wire power", utilities.getParameterBool("DynamicWirePower", False))
    add("App::PropertyBool", "WireStretchVerification", "Wire", "Verify wire elongation", utilities.getParameterBool("WireStretchVerification", False))
    add("App::PropertyLength", "WireStretchLength", "Wire", "Wire elongation before breaking", utilities.getParameterFloat("WireStretchLength", 0.0))
    add("App::PropertyLength", "KerfCompensation", "Kerf Compensation", "Kerf compensation", utilities.getParameterFloat("KerfCompensation", 0.7))
    add("App::PropertyFloat", "CompensationDegree", "Kerf Compensation", "Kerf compensation coefficient", utilities.getParameterFloat("CompensationDegree", 1.0))

    add("App::PropertyLength", "DiscretizationStep", "GCODE", "Discretization step", 0.5)
    add("App::PropertyString", "CutCommand", "GCODE", "Command for move while cutting", utilities.getParameterString("CutCommand", "G01 {Position} F{FeedRate} {WirePower}"))
    add("App::PropertyString", "MoveCommand", "GCODE", "Command for move with cold wire", utilities.getParameterString("MoveCommand", "G00 {Position}"))
    add("App::PropertyString", "PauseCommand", "GCODE", "Command for pause movements", utilities.getParameterString("PauseCommand", "G04 P{Duration}"))
    add("App::PropertyString", "WireOnCommand", "GCODE", "Command for enable wire", utilities.getParameterString("WireOnCommand", "M03 S{WirePower}"))
    add("App::PropertyString", "WireOffCommand", "GCODE", "Command for disable wire", utilities.getParameterString("WireOffCommand", "M05"))
    add("App::PropertyString", "HomingCommand", "GCODE", "Command for homing procedure", utilities.getParameterString("HomingCommand", "$H"))
    add("App::PropertyString", "InitPositionCommand", "GCODE", "Command for initialize position", utilities.getParameterString("InitPositionCommand", "G92 {Position}"))
    add("App::PropertyString", "StartProgramCode", "GCODE", "Code at the start of the program", utilities.getParameterString("StartProgramCode", ""))
    add("App::PropertyString", "EndProgramCode", "GCODE", "Code at the end of the program", utilities.getParameterString("EndProgramCode", ""))
    if add("App::PropertyEnumeration", "CommentStyle", "GCODE", "Style of commented lines", utilities.FC_COMMENT_STYLES):
        obj.CommentStyle = utilities.FC_COMMENT_STYLES.index(utilities.getParameterString("CommentStyle", "; Comment"))
    if add("App::PropertyEnumeration", "TimeUnits", "GCODE", "Units for time in GCODE", utilities.FC_TIME_UNITS):
        obj.TimeUnits = utilities.FC_TIME_UNITS.index(utilities.getParameterString("TimeUnits", "Seconds"))
    if add("App::PropertyEnumeration", "FeedRateMode", "GCODE", "Feed rate mode", utilities.FC_FEED_RATE_MODES):
        obj.FeedRateMode = utilities.FC_FEED_RATE_MODES.index(utilities.getParameterString("FeedRateMode", "G93"))

    add("App::PropertyDistance", "SafeHeight", "Travel", "Safe height for travel", utilities.getParameterFloat("SafeHeight", 120))
    add("App::PropertyTime", "PauseDuration", "Travel", "Pause duration seconds", utilities.getParameterFloat("PauseDuration", 1.0))

    add("App::PropertyLength", "BlockWidth", "Foam Block", "Foam block size along wire", utilities.getParameterFloat("BlockWidth", 450))
    add("App::PropertyLength", "BlockLength", "Foam Block", "Foam block size along machine X axis", utilities.getParameterFloat("BlockLength", 300))
    add("App::PropertyLength", "BlockHeight", "Foam Block", "Foam block size along machine Y axis", utilities.getParameterFloat("BlockHeight", 50))
    add("App::PropertyPosition", "BlockPosition", "Foam Block", "Foam block position in machine coordinates", App.Vector(-obj.BlockWidth / 2.0, obj.HorizontalTravel / 2.0 - obj.BlockLength / 2.0, utilities.getParameterFloat("BlockPositionHeight", 6)))

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
    obj.setEditorMode("WireStretchLength", 0 if obj.WireStretchVerification else 3)


def configPropertyNames(obj):
    '''
    Return the names of the machine/process properties carried by a Job.
    Reserved object properties and FreeCAD internals (underscore prefixed)
    are not configuration.
    '''
    return [name for name in obj.PropertiesList
            if name not in RESERVED_PROPERTIES and not name.startswith("_")]
