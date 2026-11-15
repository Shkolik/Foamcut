# -*- coding: utf-8 -*-

__title__ = "Exit GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Exit view provider and command."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import Part
import FoamCutViewProviders
import MovementGui
from utilities import getIconPath, getAllSelectedObjects, getWorkingPlanes, getActiveJob, requireActiveJob
import WireExit


class WireExitVP(FoamCutViewProviders.FoamCutMovementViewProvider):
    def getIcon(self):
        return getIconPath("exit.svg")

    def claimChildren(self):
        return [self.Object.ExitPoint[0]] if self.Object.ExitPoint is not None and len(self.Object.ExitPoint) > 0 else None


class MakeExit():
    """Make Exit"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("exit.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create exit",
                "ToolTip" : "Create exit path object from selected entry point"}

    def Activated(self):
        doc = App.ActiveDocument

        group = requireActiveJob("Cannot create Exit", doc)
        if group is None:
            return

        # - Get selecttion
        objects = getAllSelectedObjects()

        exit = None
        label = ""
        try:
            # - Create object
            exit = WireExit.createExit(group, objects[0], recompute = False)
            WireExitVP(exit.ViewObject)
            exit.ViewObject.PointSize = 4

            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, exit.Name)

            doc.recompute()

            MovementGui.showMovementPanel(exit, created = True)
        except Exception as error:
            App.Console.PrintError(f"Failed to create Exit.\n")
            if exit:
                label = f"{exit.Label}: "
                doc.removeObject(exit.Name)
            App.Console.PrintError(f"{label}{error}\n")

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False

        group = getActiveJob()
        if group is None:
            return False

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


Gui.addCommand("MakeExit", MakeExit())
