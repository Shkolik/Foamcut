# -*- coding: utf-8 -*-

__title__ = "Create and initialize Job"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create and initialize Job."
__usage__ = """Create and initialize Job."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutBase
import utilities
import JobConfig
import Migration
import MachineConfig
import MachineOrigin
import FoamCut_WorkingPlane
import FoamBlock
import RotationAxis

class Machine(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):   
        super().__init__(obj, jobName)  
        obj.Type = "Job"
        for name in ("ConfigName", "WPLName", "WPRName"):
            if not hasattr(obj, name):
                obj.addProperty("App::PropertyString", name, "", "", 5)
        if not hasattr(obj, "MigrationVersion"):
            obj.addProperty("App::PropertyInteger", "MigrationVersion", "", "", 5)
        obj.MigrationVersion = Migration.CURRENT_VERSION

        JobConfig.applyConfigProperties(obj)

        obj.setEditorMode("Group",     3)
        obj.Proxy = self

    def execute(self, obj):
        pass

    def onChanged(self, obj, prop):
        # - hidden _Job links do not create a dependency edge, so a
        #   config change must explicitly touch the children that read it.
        if prop in JobConfig.CONFIG_PROPERTIES:
            for child in obj.Group:
                if hasattr(child, "touch"):
                    child.touch()

        if prop == "FiveAxisMachine":
            if hasattr(obj, "OriginRotationX"):
                obj.setEditorMode("OriginRotationX", 0 if obj.FiveAxisMachine else 3)
            if hasattr(obj, "R1AxisName"):
                obj.setEditorMode("R1AxisName", 0 if obj.FiveAxisMachine else 3)
            if hasattr(obj, "ParkR1"):
                obj.setEditorMode("ParkR1", 0 if obj.EnableParking and obj.FiveAxisMachine else 3)
            if hasattr(obj, "HomingR1"):
                obj.setEditorMode("HomingR1", 0 if obj.EnableHoming and obj.FiveAxisMachine else 3)
        if prop == "EnableParking":
            for name in ("ParkX", "ParkZ", "ParkR1"):
                if hasattr(obj, name):
                    obj.setEditorMode(name, 0 if obj.EnableParking else 3)
        if prop == "EnableHoming":
            for name in ("HomingCommand", "HomingX1", "HomingX2", "HomingZ1", "HomingZ2", "HomingR1"):
                if hasattr(obj, name):
                    obj.setEditorMode(name, 0 if obj.EnableHoming else 3)
        if prop == "WireStretchVerification" and hasattr(obj, "WireStretchLength"):
            obj.setEditorMode("WireStretchLength", 0 if obj.WireStretchVerification else 3)

    def onDocumentRestored(self, obj):
        # - Migration is user-confirmed after the document is fully restored;
        #   do not touch the document from this callback.
        for child in obj.Group:
            if hasattr(child, 'Type') and child.Type == "Helper" and child.Name not in [obj.WPLName, obj.WPRName]:
                if child.ViewObject is not None:
                    utilities.setPickStyle(child.ViewObject, utilities.UNPICKABLE)

class InitMachine():
    """Init machine"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("foamcut.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Init machine",
                "ToolTip" : "Create the Job and edit machine geometry, working area and process settings"}

    def Activated(self):     
        doc = FreeCAD.ActiveDocument
        # - Create group
        machine = doc.addObject("App::DocumentObjectGroupPython", "Job")
        try:
            Machine(machine, machine.Name)
            import MachineGui
            MachineGui.MachineVP(machine.ViewObject)

            Gui.ActiveDocument.ActiveView.setActiveObject('group', machine)

            doc.recompute()
        except Exception as error:
            App.Console.PrintError("Failed to create Job.\n")
            if machine.Document is not None:
                doc.removeObject(machine.Name)
            App.Console.PrintError("{}\n".format(error))
            return

        try:
            MachineGui.showJobPanel(machine, created = True)
        except Exception as error:
            # - The Job is valid; only the editor failed to open.
            App.Console.PrintError("Could not open the Job task panel.\n")
            App.Console.PrintError("{}\n".format(error))

    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            for obj in App.ActiveDocument.Objects:
                if hasattr(obj, "Type") and obj.Type == "Job":
                    return False
        return True

Gui.addCommand("InitMachine", InitMachine())


def __getattr__(name):
    # - Old documents stored the Job view provider as InitMachine.MachineVP.
    if name == "MachineVP":
        from MachineGui import MachineVP
        return MachineVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
