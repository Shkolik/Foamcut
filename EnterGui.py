# -*- coding: utf-8 -*-

__title__ = "Enter GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Enter view provider and command."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import Part
import FoamCutViewProviders
import MovementGui
from utilities import getIconPath, getAllSelectedObjects, getWorkingPlanes
import WireEnter


class WireEnterVP(FoamCutViewProviders.FoamCutMovementViewProvider):
    def getIcon(self):
        return getIconPath("enter.svg")

    def claimChildren(self):
        return [self.Object.EntryPoint[0]] if self.Object.EntryPoint is not None and len(self.Object.EntryPoint) > 0 else None


class MakeEnter():
    """Make Enter"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("enter.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create enter",
                "ToolTip" : "Create enter path object to selected entry point"}

    def Activated(self):
        doc = App.ActiveDocument
        view = Gui.ActiveDocument.ActiveView

        group = view.getActiveObject("group")
        setActive = False
        # - if machine is not active, try to select first one in a document
        if group is None or group.Type != "Job":
            group = doc.getObject("Job")
            setActive = True

        if group is not None and group.Type == "Job":
            if setActive:
                view.setActiveObject("group", group)

            # - Get selecttion
            objects = getAllSelectedObjects()

            enter = None
            label = ""
            try:
                # - Create object
                enter = WireEnter.createEnter(group, objects[0], recompute = False)
                WireEnterVP(enter.ViewObject)
                enter.ViewObject.PointSize = 4

                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(doc.Name, enter.Name)

                doc.recompute()

                MovementGui.showMovementPanel(enter, created = True)
            except Exception as error:
                App.Console.PrintError(f"Failed to create Enter.\n")
                if enter:
                    label = f"{enter.Label}: "
                    doc.removeObject(enter.Name)
                App.Console.PrintError(f"{label}{error}\n")

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")

            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":
                # - Get selecttion
                objects = getAllSelectedObjects()

                # - nothing selected
                if len(objects) == 0:
                    return False

                object = objects[0]
                parent = object[0]
                vertex = parent.getSubObject(object[1][0])
                # - Check object type
                if not issubclass(type(vertex), Part.Vertex):
                    return False

                wp = getWorkingPlanes(group, App.ActiveDocument)
                if wp is None or len(wp) != 2:
                    return False

                return True
            return False


Gui.addCommand("MakeEnter", MakeEnter())
