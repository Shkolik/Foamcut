# -*- coding: utf-8 -*-

__title__ = "Move GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Move view provider and command."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import Part
import FoamCutViewProviders
import MovementGui
from utilities import getIconPath, getAllSelectedObjects, getWorkingPlanes, getActiveJob, requireActiveJob
import WireMove


class WireMoveVP(FoamCutViewProviders.FoamCutMovementViewProvider):
    def getIcon(self):
        return getIconPath("move.svg")

    def claimChildren(self):
        return [self.Object.StartPoint[0]] if self.Object.StartPoint is not None and len(self.Object.StartPoint) > 0 else None


class MakeMove():
    """Make Move"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("move.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create move path",
                "ToolTip" : "Create move path object from selected point in specified direction"}

    def Activated(self):
        doc = App.ActiveDocument

        group = requireActiveJob("Cannot create Move", doc)
        if group is None:
            return

        # - Get selecttion
        objects = getAllSelectedObjects()

        move = None
        label = ""
        try:
            # - Create object
            move = WireMove.createMove(group, objects[0], recompute = False)
            WireMoveVP(move.ViewObject)
            move.ViewObject.PointSize = 4

            Gui.Selection.clearSelection()
            doc.recompute()
            Gui.Selection.addSelection(doc.Name, move.Name)

            MovementGui.showMovementPanel(move, created = True)

        except Exception as error:
            App.Console.PrintError(f"Failed to create Move.\n")
            if move:
                label = f"{move.Label}: "
                doc.removeObject(move.Name)
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


Gui.addCommand("MakeMove", MakeMove())
