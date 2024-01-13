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

class Machine:
    def __init__(self, obj):
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
        
        

        # - Create CNC support
        # cnc = FreeCAD.ActiveDocument.addObject("PartDesign::Body", "CNC")
        # cnc.setEditorMode("Placement",    3)
        # cnc.setEditorMode("Label",        3)
        # cnc.setEditorMode("Tip",          3)
        # cnc.setEditorMode("BaseFeature",  3)
        # cnc.setEditorMode("Group",        3)

        # - Create working plane #L
        # wpl = cnc.newObject("PartDesign::Plane", "WPL")
        # wpl.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))
        # wpl.Support          = None
        # wpl.MapMode          = 'Deactivated'
        # wpl.MapPathParameter = 0.000000
        # wpl.MapReversed      = False
        # wpl.ResizeMode       = 'Manual'
        # wpl.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(1,0,0),90)).multiply(wpl.Placement)
        # wpl.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),-90)).multiply(wpl.Placement)
        

        # - Create working plane #R
        # wpr = cnc.newObject("PartDesign::Plane", "WPR")
        # wpr.AttachmentOffset = App.Placement(App.Vector(0.0000000000, 0.0000000000, 0.0000000000),  App.Rotation(0.0000000000, 0.0000000000, 0.0000000000))
        # wpr.Support          = None
        # wpr.MapMode          = 'Deactivated'
        # wpr.MapPathParameter = 0.000000
        # wpr.MapReversed      = False
        # wpr.ResizeMode       = 'Manual'
        # wpr.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(1,0,0),90)).multiply(wpr.Placement)
        # wpr.Placement        = App.Placement(App.Vector(0,0,0), App.Rotation(App.Vector(0,0,1),90)).multiply(wpr.Placement)
        

        # - Create CNC configuration
        config = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Config")
        Config.createConfig(config)

        # wpl.setExpression(".Width",   u"<<Config>>.VerticalTravel")
        # wpl.setExpression(".Length",    u"<<Config>>.HorizontalTravel")
        # wpl.setExpression(".Placement.Base.x", u"-<<Config>>.FieldWidth / 2")
        # wpl.setExpression(".Placement.Base.z", u"<<Config>>.VerticalTravel / 2")
        # wpl.recompute()

        # wpr.setExpression(".Width",   u"<<Config>>.VerticalTravel")
        # wpr.setExpression(".Length",    u"<<Config>>.HorizontalTravel")
        # wpr.setExpression(".Placement.Base.x", u"<<Config>>.FieldWidth / 2")
        # wpr.setExpression(".Placement.Base.z", u"<<Config>>.VerticalTravel / 2")
        # wpr.recompute()

        # - Create group
        machine = FreeCAD.ActiveDocument.addObject("App::DocumentObjectGroupPython", "Machine")
        Machine(machine)
        MachineVP(machine.ViewObject)
        machine.Group = [config]

        FreeCAD.ActiveDocument.ActiveView.setActiveObject('group', machine)

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