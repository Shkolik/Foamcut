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
import Part
import utilities

'''
  Synchronize direction of two edges using their end vertexes
  @return (vertex00, vertex01, vertex10, vertex11)
'''
def getSynchronizedVertices(first, second):
    dist, vectors, info = first.distToShape(second)
    v1, v2 = vectors[0]

    return (
        first.firstVertex()   if first.firstVertex().Point == v1  else first.lastVertex(),
        first.lastVertex()    if first.firstVertex().Point == v1  else first.firstVertex(),
        second.firstVertex()  if second.firstVertex().Point == v2 else second.lastVertex(),
        second.lastVertex()   if second.firstVertex().Point == v2 else second.firstVertex(),
    )

'''
  Make path on working planes by two sets of points
  @param first - First points set
  @param second - Second points set
  @param planes - Array of planes
  @return Array of points of intersection for each plane
'''
def makePathByPointSets(first, second, planes):
    # - Point sets must contain same number of point
    if len(first) != len(second):
        return None

    # - Check working planes count
    if len(planes) == 0:
        return None

    # - Initialize result
    result = []

    # - Intersect line by each point pair and each plane
    for plane_index in range(len(planes)):
        plane_points = []
        for point_index in range(len(first)):
            plane_points.append(
                utilities.intersectLineAndPlane(first[point_index], second[point_index], planes[plane_index])
            )
        result.append(plane_points)

    # - Done
    return result

'''
  Make path on working planes by two edges, vertices, or their combination
  @param first - First edge / vertex
  @param second - Second edge / vertex
  @param step - Distance between points in edge discretization
'''
def makePathPointsByEdgesPair(first, second, planes, invertEdge = False, step = 0.1):
    # --- Use only end vertices of coplanar edges or lines because path will be a straight line
    if first.isCoplanar(second) or (first.ShapeType == "Edge" and first.Curve.TypeId == "Part::GeomLine" and  second.ShapeType == "Edge" and second.Curve.TypeId == "Part::GeomLine"):
        
        # - Synchronize edges direction
        # TODO: Fix inacurate determination of points pair - sometimes it got flipped
        # for now there is dirty fix with InvertEdge property on path, but at least it makes 
        # Path tool less annoying
        v00, v01, v10, v11 = getSynchronizedVertices(first, second)
        
        # - try to fix calculation error
        if invertEdge:
            if v00.Point != v01.Point:
                vtemp = v00
                v00 = v01
                v01 = vtemp
            else:
                vtemp = v10
                v10 = v11
                v11 = vtemp

        # - Make path
        return makePathByPointSets([v00.Point, v01.Point], [v10.Point, v11.Point], planes)

    # --- This not coplanar edges
    else:
        # - Detect vertex and vertex
        if first.ShapeType == "Vertex" and second.ShapeType == "Vertex":
            return makePathByPointSets([first.Point], [second.Point], planes)

        # - Detect line with combination of vertex or another line
        if                                                                                                                                                  \
        (first.ShapeType == "Edge" and first.Curve.TypeId == "Part::GeomLine" and second.ShapeType == "Vertex")                                             \
        or                                                                                                                                                  \
        (first.ShapeType == "Vertex" and second.ShapeType == "Edge" and second.Curve.TypeId == "Part::GeomLine")                                            \
        :
            # - Simplify path to straight line
            points_count = 2
        else:
            # - Find longest edge
            maxlen = first.Length if first.Length >= second.Length else second.Length

            # - Calculate number of discretization points
            points_count = int(float(maxlen) / float(step))

    print("Point count = %d" % points_count)

    first_set   = []
    second_set  = []

    # - Discretize first edge
    if first.ShapeType == "Vertex":
        for i in range(points_count): first_set.append(first.Point)
    else:
        first_set = first.discretize(Number=points_count) if points_count > 2 else [first.firstVertex().Point, first.lastVertex().Point]

    # - Discretize second edge
    if second.ShapeType == "Vertex":
        for i in range(points_count): second_set.append(second.Point)
    else:
        second_set = second.discretize(Number=points_count) if points_count > 2 else [second.firstVertex().Point, second.lastVertex().Point]

    # - Make path
    return makePathByPointSets(first_set, second_set, planes)

class PathSection:
    def __init__(self, obj, edge_l, edge_r):
        obj.addProperty("App::PropertyVectorList",  "Path_L",     "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Path_R",     "", "", 5)
        obj.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Path"

        obj.addProperty("App::PropertyLinkSub",     "LeftEdge",             "Edges",    "Left Edge").LeftEdge = edge_l
        obj.addProperty("App::PropertyLinkSub",     "RightEdge",            "Edges",    "Right Edge").RightEdge = edge_r
        obj.addProperty("App::PropertyBool",        "InvertEdge",           "Edges",    "Check in case of obvious error in calculations").InvertEdge = False

        obj.addProperty("App::PropertyInteger",     "PointsCount",          "Information", "Number of points", 1)
        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",    "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",   "Information", "Right Segment length",   1)

        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(self, obj):
        # - Get working planes
        wp = utilities.getWorkingPlanes()
        
        edge_l = obj.LeftEdge[0].getSubObject(obj.LeftEdge[1])[0]
        edge_r = obj.RightEdge[0].getSubObject(obj.RightEdge[1])[0]
        
        # - Make path between objects on working planes
        path_points = makePathPointsByEdgesPair(edge_l, edge_r, wp, obj.InvertEdge)

        # - Set data
        obj.Path_L       = [App.Vector(item.X, item.Y, item.Z) for item in path_points[0]]
        obj.Path_R       = [App.Vector(item.X, item.Y, item.Z) for item in path_points[1]]        
        obj.PointsCount  = int(len(path_points[0]))
        #

        # - Create path for L
        path_L = Part.BSplineCurve()
        path_L.approximate(Points = obj.Path_L, Continuity="C0")

        # - Create path for R
        path_R = Part.BSplineCurve()
        path_R.approximate(Points = obj.Path_R, Continuity="C0")

        # - Update shape and information
        obj.Shape = Part.makeCompound([path_L.toShape(), path_R.toShape(), Part.Wire(edge_l), Part.Wire(edge_r)])
        obj.LeftSegmentLength = float(path_L.length())
        obj.RightSegmentLength = float(path_R.length())

        Gui.Selection.clearSelection()

class PathSectionVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("path.svg")

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
        

    def claimChildren(self):
        return [self.Object.LeftEdge[0], self.Object.RightEdge[0]]
    
class MakePath():
    """Make Path"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("path.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create path",
                "ToolTip" : "Create path object from 2 selected opposite edges"}

    def Activated(self):
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":
            # - Get selected edges
            edges = utilities.getAllSelectedEdges()
            obj = FreeCAD.ActiveDocument.addObject("Part::FeaturePython","Path")
            
            PathSection(obj, (FreeCAD.ActiveDocument.getObject((edges[0])[0].Name), (edges[0])[1][0]), (FreeCAD.ActiveDocument.getObject((edges[1])[0].Name),(edges[1])[1][0]))
            PathSectionVP(obj.ViewObject)
            obj.ViewObject.PointSize = 4

            group.addObject(obj)
            obj.recompute()
    
    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            # - Get selected edges
            edges = utilities.getAllSelectedEdges()

            # - Number of edges should be two
            if len(edges) != 2:               
                return False
            
            if len(utilities.getWorkingPlanes()) != 2:
                return False
                
            return True
            
Gui.addCommand("MakePath", MakePath())
