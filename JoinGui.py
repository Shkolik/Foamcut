# -*- coding: utf-8 -*-

__title__ = "Join GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Join view provider and command."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import FoamCutViewProviders
import MovementGui
import utilities
from utilities import getAllSelectedObjects, isMovement
import WireJoin


class WireJoinVP(FoamCutViewProviders.FoamCutMovementViewProvider):
    def getIcon(self):
        return utilities.getIconPath("join.svg")

    def claimChildren(self):
        if (self.Object.StartPoint is not None and len(self.Object.StartPoint) > 0
            and self.Object.EndPoint is not None and len(self.Object.EndPoint) > 0 ):
            return [self.Object.StartPoint[0], self.Object.EndPoint[0]]
        return None


class MakeJoin():
    """Make Join"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("join.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Join 2 points",
                "ToolTip" : "Join 2 selected points"}

    def Activated(self):
        doc = App.ActiveDocument

        group = utilities.requireActiveJob("Cannot create Join", doc)
        if group is None:
            return

        # - Get selecttion
        objects = getAllSelectedObjects()

        join = None
        label = ""
        try:
            # - Create object
            join = WireJoin.createJoin(group, objects[0], objects[1], recompute = False)
            WireJoinVP(join.ViewObject)
            join.ViewObject.PointSize = 4

            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, join.Name)
            doc.recompute()

            MovementGui.showMovementPanel(join, created = True)
        except Exception as error:
            App.Console.PrintError(f"Failed to create Join.\n")
            if join:
                label = f"{join.Label}: "
                doc.removeObject(join.Name)
            App.Console.PrintError(f"{label}{error}\n")

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False

        group = utilities.getActiveJob()
        if group is None:
            return False

        # - Pre-0.2.1 documents are not migrated yet: their settings
        #   are not on the Job, so a new object would bind broken
        #   expressions. Let the migration run first.
        if not hasattr(group, "FieldWidth"):
            return False

        # - Get selecttion
        objects = getAllSelectedObjects()

        # - nothing selected
        if len(objects) < 2:
            return False

        parentA = objects[0][0]
        parentB = objects[1][0]
        # - Check object type
        return isMovement(parentA) or isMovement(parentB)


Gui.addCommand("Join", MakeJoin())
