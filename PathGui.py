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
from utilities import getIconPath, getAllSelectedObjects, getWorkingPlanes, getEdgesLinks, getActiveJob, requireActiveJob
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

    def FindOppositeEdgeIndex(self, edge, edges_r, skipIndex=None):
        """
        Try to find edge in collection of edges that most close to edge provided

        @param edge - edge on a left side
        @param edges_r - edges on a right side
        @param skipIndex - index of edge to skip in edges_r

        @returns index of closest edge on a right side
        """
        v1_l = edge.firstVertex().Point
        v2_l = edge.lastVertex().Point

        firstRightEdgeIndex = skipIndex + 1 if skipIndex is not None and skipIndex + 1 < len(edges_r) else 0

        minDistance = min(v1_l.distanceToPoint(edges_r[firstRightEdgeIndex].firstVertex().Point), v1_l.distanceToPoint(edges_r[firstRightEdgeIndex].lastVertex().Point)) + \
        min(v2_l.distanceToPoint(edges_r[firstRightEdgeIndex].firstVertex().Point), v2_l.distanceToPoint(edges_r[firstRightEdgeIndex].lastVertex().Point))

        for i, edge_r in enumerate(edges_r):
            if( i == skipIndex):
                continue
            v1_r = edge_r.firstVertex().Point
            v2_r = edge_r.lastVertex().Point
            dist = min(v1_l.distanceToPoint(v1_r), v1_l.distanceToPoint(v2_r)) + min(v2_l.distanceToPoint(v1_r), v2_l.distanceToPoint(v2_r))
            if dist < minDistance:
                minDistance = dist
                firstRightEdgeIndex = i

        return firstRightEdgeIndex

    def SortEdges(self, parent_l, parent_r, edges_l, edges_r):
        """
        Sort right edges to form opposite edge pairs

        @param parent_l - feature containing edges_l
        @param parent_r - feature containing edges_r
        @param edges_l - list of edges on a left side
        @param edges_r - list of edges on a right side

        @returns list of edge pairs
        """

        objects = []

        if len(edges_l) == 1 and len(edges_r) == 1:
            edges_l_links = getEdgesLinks(parent_l, edges_l)
            edges_r_links = getEdgesLinks(parent_r, edges_r)
            if len(edges_l_links) == 0 or len(edges_r_links) == 0:
                FreeCAD.Console.PrintError("ERROR: Cannot create paths. Selected edges have no matching links in the parent shape.\n")
                return objects
            objects.append([edges_l_links[0], edges_r_links[0]])
            return objects

        firstRightEdgeIndex = self.FindOppositeEdgeIndex(edges_l[0], edges_r)
        secondRightEdgeIndex = self.FindOppositeEdgeIndex(edges_l[1], edges_r, firstRightEdgeIndex)

        edges_r_sorted = []

        if (firstRightEdgeIndex + 1 == len(edges_r) and secondRightEdgeIndex == 0) or firstRightEdgeIndex < secondRightEdgeIndex:
            for i in range(firstRightEdgeIndex, len(edges_r)):
                edges_r_sorted.append(edges_r[i])
            for i in range(firstRightEdgeIndex):
                edges_r_sorted.append(edges_r[i])
        else:
            for i in range(firstRightEdgeIndex, -1, -1):
                edges_r_sorted.append(edges_r[i])
            for i in range(len(edges_r) - 1, firstRightEdgeIndex, - 1):
                edges_r_sorted.append(edges_r[i])

        edges_l_links = getEdgesLinks(parent_l, edges_l)
        edges_r_links = getEdgesLinks(parent_r, edges_r_sorted)

        if len(edges_l_links) < len(edges_l) or len(edges_r_links) < len(edges_r_sorted):
            FreeCAD.Console.PrintError("ERROR: Cannot create paths. Selected edges have no matching links in the parent shape.\n")
            return objects

        for i in range(len(edges_l)):
            objects.append([edges_l_links[i], edges_r_links[i]])

        return objects

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

            edgesPairs = self.SortEdges(objects[0][0] if not right else objects[1][0], objects[1][0] if not right else objects[0][0], edges_l, edges_r)

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
