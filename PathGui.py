# -*- coding: utf-8 -*-

__title__ = "Path GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Path view provider and command."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import FoamCutViewProviders
import MovementGui
from utilities import getIconPath, getAllSelectedObjects, getWorkingPlanes, getEdgesLinks, getActiveJob, requireActiveJob, sortEdges
import WirePath


class PathSectionVP(FoamCutViewProviders.FoamCutMovementViewProvider):

    def getIcon(self):
        return getIconPath("path.svg")

    def claimChildren(self):
        if (self.Object.LeftEdge is not None and len(self.Object.LeftEdge) > 0
            and self.Object.RightEdge is not None and len(self.Object.RightEdge) > 0 ):
            return [self.Object.LeftEdge[0], self.Object.RightEdge[0]] if self.Object.LeftEdge[0] != self.Object.RightEdge[0] else [self.Object.LeftEdge[0]]
        return None


class MakePath():
    """Make Path"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("path.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create path",
                "ToolTip" : "Create path object from 2 selected opposite edges or faces. If 2 faces selected, separate path will be created for each edge pair."}

    def CreateFromEdges(self, edges, group):
        path = None
        label = ""
        try:
            path = WirePath.createPath(group,
                                       (edges[0][0], (edges[0])[1][0]),
                                       (edges[1][0], (edges[1])[1][0]),
                                       recompute = False)
            PathSectionVP(path.ViewObject)
            path.ViewObject.PointSize = 4
        except Exception as error:
            App.Console.PrintError(f"Failed to create Path.\n")
            if path:
                label = f"{path.Label}: "
                path.Document.removeObject(path.Name)
            App.Console.PrintError(f"{label}{error}\n")
            path = None

        return path

    def Activated(self):
        doc = App.ActiveDocument

        group = requireActiveJob("Cannot create paths", doc)
        if group is None:
            return

        # - Get selected objects
        objects = getAllSelectedObjects(True)

        # left working plane
        wps = getWorkingPlanes(group, App.ActiveDocument)

        baseObjects = []

        edges_l = []
        edges_r = []

        edgesPairs = []

        firstSub = objects[0][0].getSubObject(objects[0][1][0])
        (dist_l, _, _) = firstSub.distToShape(wps[0].Shape) # distance to left working plane
        (dist_r, _, _) = firstSub.distToShape(wps[1].Shape) # distance to right working plane

        right = dist_l > dist_r

        for object in objects:
            if object[1][0].startswith("Face"):
                # - prepare base object.
                # - Sometimes, after reopening file it is necessary to recompute em or list of edges will be empty
                if object[0].Name not in baseObjects:
                    object[0].touch()
                    baseObjects.append(object[0].Name)
                    object[0].recompute(True)

                if right:
                    edges_r = object[0].getSubObject(object[1][0]).Edges
                    right = False
                else:
                    edges_l = object[0].getSubObject(object[1][0]).Edges
                    right = True
            else:
                edgesPairs.append(objects)
                break

        # - Face selection: create paths for each edge pair
        if objects[0][1][0].startswith("Face"):
            #reset
            right = dist_l > dist_r

            if len(edges_l) == 0 or len(edges_r) == 0:
                FreeCAD.Console.PrintError("ERROR: Cannot create paths. No edges found in the selected faces.\n")
                return
            elif len(edges_l) != len(edges_r):
                FreeCAD.Console.PrintError("ERROR: Cannot create paths. Selected faces have different edge counts ({} vs {}). Select faces with the same number of edges.\n".format(len(edges_l), len(edges_r)))
                return

            edgesPairs = sortEdges(objects[0][0] if not right else objects[1][0], objects[1][0] if not right else objects[0][0], edges_l, edges_r)

            if not edgesPairs:
                return

        created = []
        for pair in edgesPairs:
            path = self.CreateFromEdges(pair, group)
            if path is not None:
                created.append(path)

        doc.recompute()
        Gui.Selection.clearSelection()

        if len(created) == 1:
            Gui.Selection.addSelection(doc.Name, created[0].Name)
            MovementGui.showMovementPanel(created[0], created = True)
        elif created:
            for path in created:
                Gui.Selection.addSelection(doc.Name, path.Name)
            App.Console.PrintMessage("{} paths created. Double-click a path to edit settings.\n".format(len(created)))

    def IsActive(self):
        if App.ActiveDocument is None:
            return False

        group = getActiveJob()
        if group is None:
            return False

        # - Get selected objects
        objects = getAllSelectedObjects(True)

        # - Number of edges or faces should be 2
        if len(objects) != 2:
            return False

        # - supported selected objects combinations is:
        # - Face and Face
        # - Edge and Edge
        # - Vertex and Vertex
        object1 = objects[0]
        object2 = objects[1]

        def selectionKind(sub):
            for kind in ("Face", "Edge", "Vertex"):
                if sub.startswith(kind):
                    return kind
            return ""

        if selectionKind(object1[1][0]) != selectionKind(object2[1][0]):
            return False

        wp = getWorkingPlanes(group, App.ActiveDocument)
        if wp is None or len(wp) != 2:
            return False
        return True


Gui.addCommand("MakePath", MakePath())
