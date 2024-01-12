# -*- coding: utf-8 -*-

__title__ = "Foamcut workbench utilities"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Foamcut workbench utilities common to all tools."

import FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import os

'''
    Returns the current module path.
    Determines where this file is running from, so works regardless of whether
    the module is installed in the app's module directory or the user's app data folder.
    (The second overrides the first.)
'''
def get_module_path():    
    return os.path.dirname(__file__)

def getIconPath(icon):
    return os.path.join(get_module_path(), "Resources", "icons", icon)

def isNewStateHandling():
    return (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]+FreeCAD.Version()[2]) >= '0.212' and (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]) < '2000'
    
'''
  Get all selected Edges and Vertexes
'''
def getAllSelectedObjects():
    objects = []
    for obj in  Gui.Selection.getSelectionEx():
        if obj.HasSubObjects:
            i = 0
            for subobj in obj.SubObjects:
                if issubclass(type(subobj), Part.Edge) or issubclass(type(subobj), Part.Vertex):
                    objects.append((obj.Object, [obj.SubElementNames[i]]))
                i += 1
    return objects

'''
  Get all selected Edges
'''
def getAllSelectedEdges():
    objects = []
    for obj in  Gui.Selection.getSelectionEx():
        if obj.HasSubObjects:
            i = 0
            for subobj in obj.SubObjects:
                if issubclass(type(subobj), Part.Edge):
                    objects.append((obj.Object, [obj.SubElementNames[i]]))
                i += 1
    return objects

'''
  Check if points are common
  @param first - Fist point
  @param second - Second point
  @return True if point are common
'''
def isCommonPoint(first, second):
    return True if first.distanceToPoint(second) < 0.01 else False
  
'''
  Find point of intersection of line and plane
  @param v0 - Fist point
  @param v1 - Second point
  @return Point of intersection
'''
def intersectLineAndPlane(v0, v1, plane):
    # - Check is same points and move one of them along X axis to make able to make a line
    if (v0.isEqual(v1, 0.01)):
        v1.x += 1

    # - Make line
    edge  = Part.makeLine(v0, v1);

    # - Find point of intersection
    point = plane.Shape.Surface.intersect(edge.Curve)[0][0]
    del edge
    return point

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
            intersectLineAndPlane(first[point_index], second[point_index], planes[plane_index])
            )
        result.append(plane_points)


    # - Done
    return result

'''
  Get working planes
'''
def getWorkingPlanes():
        doc = FreeCAD.activeDocument()
        # - Initialize result
        result = []
        wpl = doc.getObjectsByLabel('WPL')
        if len(wpl) > 0:
            result.append(wpl[0])
        else:
            print("ERROR: Left working plane not found")
            return None
        wpr = doc.getObjectsByLabel('WPR')
        if len(wpr) > 0:
            result.append(wpr[0])
        else:
            print("ERROR: Right working plane not found")
        
        return result
        
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
  Make path on working planes by two edges, vertices, or their combination
  @param first - First edge / vertex
  @param second - Second edge / vertex
  @param step - Distance between points in edge discretization
'''
def makePathPointsByEdgesPair(first, second, planes, step = 0.1):
    # --- Use only end vertices of coplanar edges or lines because path will be a straight line
    if first.isCoplanar(second) or (first.ShapeType == "Edge" and first.Curve.TypeId == "Part::GeomLine" and  second.ShapeType == "Edge" and second.Curve.TypeId == "Part::GeomLine"):
        # - Synchronize edges direction
        v00, v01, v10, v11 = getSynchronizedVertices(first, second)

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