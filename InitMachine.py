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
import FoamCutViewProviders
import FoamCutBase
import utilities
import MachineConfig
import MachineOrigin
import FoamCut_WorkingPlane
import FoamBlock
import RotationAxis

def initChildren(config, machine):
    origin = machine.newObject("App::FeaturePython", "Origin")
    MachineOrigin.CreateOrigin(origin, machine.Name)

    CNCVolume = machine.newObject("Part::Box", "CNCVolume")
    CNCVolume.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Helper"
    CNCVolume.setEditorMode("Placement",     3)
    CNCVolume.setEditorMode("Label",         3)
    CNCVolume.setEditorMode("Width",         3)
    CNCVolume.setEditorMode("Height",        3)
    CNCVolume.setEditorMode("Length",        3)
    CNCVolume.setEditorMode("MapMode",       3)

    CNCVolume.setExpression(".Placement.Base.y", u"-<<{}>>.OriginX".format(config.Name))
    CNCVolume.setExpression(".Placement.Base.x", u"- <<{}>>.FieldWidth / 2".format(config.Name))
    CNCVolume.setExpression(".Length",   u"<<{}>>.FieldWidth".format(config.Name))
    CNCVolume.setExpression(".Width",   u"<<{}>>.HorizontalTravel".format(config.Name))
    CNCVolume.setExpression(".Height",   u"<<{}>>.VerticalTravel".format(config.Name))
    CNCVolume.ViewObject.Transparency = 90
    CNCVolume.ViewObject.LineWidth = 1.0
    CNCVolume.ViewObject.PointSize = 1.0
    CNCVolume.ViewObject.ShapeColor = (190, 190, 190)
    utilities.setPickStyle(CNCVolume.ViewObject, utilities.UNPICKABLE)
    
    wpl = machine.newObject("Part::FeaturePython", "WPL")
    FoamCut_WorkingPlane.CreateWorkingPlane(wpl, machine.Name, utilities.LEFT)
    wpl.Label = "Working Plane L"

    machine.WPLName = wpl.Name
    
    wpr = machine.newObject("Part::FeaturePython", "WPR")
    FoamCut_WorkingPlane.CreateWorkingPlane(wpr, machine.Name, utilities.RIGHT)
    wpr.Label = "Working Plane R"

    machine.WPRName = wpr.Name

    block = machine.newObject("Part::FeaturePython", "Block")
    FoamBlock.CreateFoamBlock(block, machine.Name)
    block.Label = "Foam Block"

    if config.FiveAxisMachine:
        axis = machine.newObject("App::FeaturePython", "RotationAxis")    
        axis.Label = "Rotation Axis"
        RotationAxis.CreateRotationAxis(axis, machine.Name)

class Machine(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):   
        super().__init__(obj, jobName)  
        obj.Type = "Job"
        obj.addProperty("App::PropertyString",      "ConfigName", "", "", 5)
        obj.addProperty("App::PropertyString",      "WPLName", "", "", 5)
        obj.addProperty("App::PropertyString",      "WPRName", "", "", 5)

        obj.setEditorMode("Group",     3)
        obj.Proxy = self

    def execute(self, obj):
        pass

class MachineVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    
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
    
class InitMachine():
    """Init machine"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("foamcut.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Init machine",
                "ToolTip" : "Create Machine object and define working area and machine properties"}

    def Activated(self):     
        # - Create group
        machine = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroupPython", "Job")
        Machine(machine, machine.Name)
        MachineVP(machine.ViewObject)

        # - Create CNC configuration
        config = machine.newObject("App::DocumentObjectGroupPython", "Config")
        MachineConfig.createConfig(config, machine.Name)

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