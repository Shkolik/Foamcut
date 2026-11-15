# -*- coding: utf-8 -*-

__title__ = "Create and initialize Job"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Job object and its script-friendly factory."
__usage__ = """Create a Job from the GUI command in MachineGui or with createMachine()."""

import FreeCAD
App=FreeCAD
import FoamCutBase
import utilities
import JobConfig
import Migration

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


def createMachine(doc, label = None, recompute = True):
    '''
    Create a Job (machine setup) in a document.
    Script-friendly entry point: no GUI is required.
    @param doc - document that will own the Job
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Job object
    '''
    machine = doc.addObject("App::DocumentObjectGroupPython", "Job")
    try:
        Machine(machine, machine.Name)
        if label:
            machine.Label = label
    except Exception:
        doc.removeObject(machine.Name)
        raise

    if recompute:
        doc.recompute()
    return machine


def __getattr__(name):
    # - Old documents stored the Job view provider as InitMachine.MachineVP.
    if name == "MachineVP":
        from MachineGui import MachineVP
        return MachineVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
