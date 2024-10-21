# -*- coding: utf-8 -*-

__title__ = "Make Path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Make Path from 2 selected opposite edges."
__usage__ = """Select 2 opposite edges and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutViewProviders
import FoamCutBase
import utilities
from utilities import getWorkingPlanes, getAllSelectedObjects, getEdgesLinks

class PathSection(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, edge_l, edge_r, jobName):
        super().__init__(obj, jobName)      
        obj.Type = "Path"

        obj.addProperty("App::PropertyLinkSub",     "LeftEdge",             "Edges",    "Left Edge").LeftEdge = edge_l
        obj.addProperty("App::PropertyLinkSub",     "RightEdge",            "Edges",    "Right Edge").RightEdge = edge_r
        
        obj.setEditorMode("KerfCompensationDirection", 3)
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj): 

        job = obj.Document.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            App.Console.PrintError("ERROR:\n Error updating Enter - active Job not found\n")

        wp = getWorkingPlanes(job, obj.Document)
      
        leftEdge = obj.LeftEdge[0].getSubObject(obj.LeftEdge[1][0])
        rightEdge = obj.RightEdge[0].getSubObject(obj.RightEdge[1][0])
        
        self.createShape(obj, [leftEdge, rightEdge], wp, (0, 0, 0))

class PathSectionVP(FoamCutViewProviders.FoamCutMovementViewProvider): 
    
    def getIcon(self):
        return utilities.getIconPath("path.svg")

    def claimChildren(self):
        if (self.Object.LeftEdge is not None and len(self.Object.LeftEdge) > 0 
            and self.Object.RightEdge is not None and len(self.Object.RightEdge) > 0 ):
            return [self.Object.LeftEdge[0], self.Object.RightEdge[0]] if self.Object.LeftEdge[0] != self.Object.RightEdge[0] else [self.Object.LeftEdge[0]]
        return None

class MakePath():
    """Make Path"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("path.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create path",
                "ToolTip" : "Create path object from 2 selected opposite edges or faces. If 2 faces selected, separate path will be created for each edge pair."}

    def CreateFromEdges(self, edges, group):
        obj = group.newObject("Part::FeaturePython","Path")
            
        PathSection(obj, 
                    (FreeCAD.ActiveDocument.getObject((edges[0])[0].Name), (edges[0])[1][0]), 
                    (FreeCAD.ActiveDocument.getObject((edges[1])[0].Name),(edges[1])[1][0]),
                    group.Name)
        PathSectionVP(obj.ViewObject)
        obj.ViewObject.PointSize = 4
        
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
        firstLeftEdge = edges_l[0]
        v1_l = firstLeftEdge.firstVertex().Point
        v2_l = firstLeftEdge.lastVertex().Point
        

        minDistance = min(v1_l.distanceToPoint(edges_r[0].firstVertex().Point), v1_l.distanceToPoint(edges_r[0].lastVertex().Point)) + \
        min(v2_l.distanceToPoint(edges_r[0].firstVertex().Point), v2_l.distanceToPoint(edges_r[0].lastVertex().Point))

        firstRightEdgeIndex = 0
        for i, edge in enumerate(edges_r):
            v1_r = edge.firstVertex().Point
            v2_r = edge.lastVertex().Point
            dist = min(v1_l.distanceToPoint(v1_r), v1_l.distanceToPoint(v2_r)) + min(v2_l.distanceToPoint(v1_r), v2_l.distanceToPoint(v2_r))
            
            if dist < minDistance:
                minDistance = dist
                firstRightEdgeIndex = i
        
        edges_r_sorted = []
        for i in range(firstRightEdgeIndex, len(edges_r)):
            edges_r_sorted.append(edges_r[i])
        for i in range(firstRightEdgeIndex):
            edges_r_sorted.append(edges_r[i])

        edges_l_links = getEdgesLinks(parent_l, edges_l)
        edges_r_links = getEdgesLinks(parent_r, edges_r_sorted)

        for i in range(len(edges_l)):
            objects.append([edges_l_links[i], edges_r_links[i]])

        return objects

    def Activated(self):
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        setActive = False
        # - if machine is not active, try to select first one in a document
        if group is None or group.Type != "Job":
            group = App.ActiveDocument.getObject("Job")
            setActive = True

        if group is not None and group.Type == "Job":
            if setActive:
                Gui.ActiveDocument.ActiveView.setActiveObject("group", group)
            
            # - Get selected objects
            objects = utilities.getAllSelectedObjects(True)

            baseObjects = []

            edges_l = []
            edges_r = []

            edgesPairs = []

            right = False
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
                    else:
                        edges_l = object[0].getSubObject(object[1][0]).Edges
                        right = True
                else:
                    edgesPairs.append(objects)
                    break

            if len(edges_l) > 1 and len(edges_l) == len(edges_r):
                #print("Left edges: {}".format(edges_l))
                #print("Right edges: {}".format(edges_r))
                edgesPairs = self.SortEdges(objects[0][0], objects[1][0], edges_l, edges_r)

            for pair in edgesPairs:
                self.CreateFromEdges(pair, group)
            
            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()
    
    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":  
                # - Get selected objects
                objects = getAllSelectedObjects(True)

                # - Number of edges should be two
                if len(objects) != 2:               
                    return False
                
                # - supported selected objects combinations is:
                # - Face and Face
                # - Edge and Edge
                # - Edge and Vertex
                # - Vertex and Edge
                object1 = objects[0]
                object2 = objects[1]
                if object1[1][0].startswith("Face") != object2[1][0].startswith("Face"):
                    return False

                wp = getWorkingPlanes(group, App.ActiveDocument)
                if wp is None or len(wp) != 2:
                    return False                    
                return True
            return False
            
Gui.addCommand("MakePath", MakePath())
