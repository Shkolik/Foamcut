# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create and initialize Job."
__usage__ = """Create and initialize Job."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import utilities
import Config
import Origin

def initChildren(config, machine):
    origin = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroupPython", "Origin")
    Origin.CreateOrigin(origin, config.Name)

    CNCVolume = FreeCAD.ActiveDocument.addObject("Part::Box", "CNCVolume")
    CNCVolume.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Helper"
    CNCVolume.setEditorMode("Placement",     3)
    CNCVolume.setEditorMode("Label",         3)
    CNCVolume.setEditorMode("Width",         3)
    CNCVolume.setEditorMode("Height",        3)
    CNCVolume.setEditorMode("Length",        3)
    CNCVolume.setEditorMode("AttachmentSupport",       3)
    CNCVolume.setEditorMode("MapMode",       3)

    CNCVolume.setExpression(".Placement.Base.y", u"<<{}>>.OriginX".format(config.Name))
    CNCVolume.setExpression(".Placement.Base.x", u"- <<{}>>.FieldWidth / 2".format(config.Name))
    CNCVolume.setExpression(".Length",   u"<<{}>>.FieldWidth".format(config.Name))
    CNCVolume.setExpression(".Width",   u"<<{}>>.HorizontalTravel".format(config.Name))
    CNCVolume.setExpression(".Height",   u"<<{}>>.VerticalTravel".format(config.Name))
    CNCVolume.ViewObject.Transparency = 90
    utilities.setPickStyle(CNCVolume.ViewObject, utilities.UNPICKABLE)
    
    RotationAxis = FreeCAD.ActiveDocument.addObject("Part::Line","RotationAxis")
    RotationAxis.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Helper"
    RotationAxis.X1 = 0
    RotationAxis.setExpression(".Y1", u"<<{}>>.OriginRotationX".format(config.Name))
    RotationAxis.Z1 = 0
    RotationAxis.X2 = 0
    RotationAxis.setExpression(".Y2", u"<<{}>>.OriginRotationX".format(config.Name))
    RotationAxis.setExpression(".Z2", u"<<{}>>.VerticalTravel + 50".format(config.Name))
    RotationAxis.Placement = App.Placement(App.Vector(0.00,0.00,0.00),App.Rotation(App.Vector(0.00,0.00,1.00),0.00))
    RotationAxis.ViewObject.PointSize = 0
    RotationAxis.ViewObject.Transparency = 70
    RotationAxis.ViewObject.LineColor = (1.0, 0.886, 0.023)
    
    WPL = FreeCAD.ActiveDocument.addObject("Part::Plane", "WPL")
    WPL.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Helper"
    WPL.Support          = None
    WPL.MapMode          = 'Deactivated'
    WPL.MapPathParameter = 0.000000
    WPL.MapReversed      = False
    WPL.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))
    WPL.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),90))
    WPL.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,1,0),90)).multiply(WPL.Placement)
    WPL.ViewObject.LineColor = (1.0, 0.886, 0.023)
    WPL.ViewObject.ShapeColor = (1.0, 0.886, 0.023)
    WPL.ViewObject.PointColor = (1.0, 0.886, 0.023)
    WPL.ViewObject.LineWidth = 0
    WPL.setExpression(".Width",   u"<<{}>>.VerticalTravel".format(config.Name))
    WPL.setExpression(".Length",  u"<<{}>>.HorizontalTravel".format(config.Name))
    WPL.setExpression(".Placement.Base.x", u"-<<{}>>.FieldWidth / 2".format(config.Name))
    WPL.Placement.Base.z = 0
    WPL.ViewObject.Transparency = 80

    machine.WPLName = WPL.Name
    
    WPR = FreeCAD.ActiveDocument.addObject("Part::Plane", "WPR")
    WPR.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Helper"
    WPR.Support          = None
    WPR.MapMode          = 'Deactivated'
    WPR.MapPathParameter = 0.000000
    WPR.MapReversed      = False
    WPR.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))        
    WPR.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),90))
    WPR.Placement = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,1,0),90)).multiply(WPR.Placement)
    WPR.ViewObject.LineColor =  (1.0, 0.886, 0.023)
    WPR.ViewObject.ShapeColor = (1.0, 0.886, 0.023)
    WPL.ViewObject.PointColor = (1.0, 0.886, 0.023)
    WPR.ViewObject.LineWidth = 0
    WPR.setExpression(".Width",   u"<<{}>>.VerticalTravel".format(config.Name))
    WPR.setExpression(".Length",  u"<<{}>>.HorizontalTravel".format(config.Name))
    WPR.setExpression(".Placement.Base.x", u"<<{}>>.FieldWidth / 2".format(config.Name))
    WPR.Placement.Base.z = 0
    WPR.ViewObject.Transparency = 80

    machine.WPRName = WPR.Name

    machine.Group = [config, origin, RotationAxis, CNCVolume, WPL, WPR]
    
class Machine:
    def __init__(self, obj):
        obj.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Job"
        obj.addProperty("App::PropertyString",      "ConfigName", "", "", 5)
        obj.addProperty("App::PropertyString",      "WPLName", "", "", 5)
        obj.addProperty("App::PropertyString",      "WPRName", "", "", 5)
        obj.Proxy = self

    def onChanged(self, fp, prop):
        pass

    def execute(self, obj):
        pass

class MachineVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        for child in self.Object.Group:
            if hasattr(child, 'Type') and child.Type == "Helper" and child.Name not in [self.Object.WPLName, self.Object.WPRName]:
                utilities.setPickStyle(child.ViewObject, utilities.UNPICKABLE)

    def doubleClicked(self, obj):
        if Gui.ActiveDocument.ActiveView.getActiveObject("group") == obj.Object:
            Gui.ActiveDocument.ActiveView.setActiveObject("group", None)
        else:
            Gui.ActiveDocument.ActiveView.setActiveObject("group", obj.Object)
        return True
    
    def getIcon(self):
        return utilities.getIconPath("machine.svg")
    
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
  
class InitMachine():
    """Init machine"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("foamcut.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Init machine",
                "ToolTip" : "Create Machine object and define working area and machine properties"}

    def Activated(self):        
        # - Create CNC configuration
        config = FreeCAD.ActiveDocument.addObject("App::FeaturePython", "Config")
        Config.createConfig(config)

        # - Create group
        machine = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroupPython", "Job")
        Machine(machine)
        MachineVP(machine.ViewObject)

        machine.ConfigName = config.Name
        initChildren(config, machine)

        Gui.ActiveDocument.ActiveView.setActiveObject('group', machine)

        FreeCAD.ActiveDocument.recompute()

    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            setup = App.ActiveDocument.getObject("Machine")
            if setup:
                return False
        return True

Gui.addCommand("InitMachine", InitMachine())