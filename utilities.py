# -*- coding: utf-8 -*-

__title__ = "Foamcut workbench utilities"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Foamcut workbench utilities common to all tools."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import os
from math import sqrt, isclose

START       = 0           # - Segment start point index
END         = -1          # - Segment end point index

LEFT = -1
RIGHT = 1

FC_TYPES = ["Path", "Projection", "Rotation", "Enter", "Exit", "Move", "Join", "Route", "Job", "Helper"]
FC_TYPES_TO_ROUTE = ["Path", "Projection", "Rotation", "Enter", "Exit", "Move", "Join"]

FC_KERF_DIRECTIONS = ["Positive", "None", "Negative"]
FC_TIME_UNITS = ["Seconds", "Milliseconds"]

'''
    Returns the current module path.
    Determines where this file is running from, so works regardless of whether
    the module is installed in the app's module directory or the user's app data folder.
    (The second overrides the first.)
'''
def get_module_path():    
    return os.path.dirname(__file__)

def getResourcesPath():
    return os.path.join(get_module_path(), "Resources")

def getIconPath(icon):
    return os.path.join(getResourcesPath(), "icons", icon)

'''
    Checks if we need handle object state in a new fashion
    It was first introduced in FC v.0.21.2 and was merged into LinkStage3 branch v.2024.113
'''
def isNewStateHandling():
    version = FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]+FreeCAD.Version()[2]
    return (version >= '0.212' and version < '2024.1130') or version >= '2024.1130'

'''
    Checks if edge is strait line
'''
def isStraitLine(edge):
    #check single edge
    if len(edge.Vertexes) == 2:
        len1 = (edge.Vertexes[0].Point - edge.Vertexes[1].Point).Length
        return isclose(abs(len1), edge.Length, rel_tol=1e-7)    
    else:
        return False


'''
    Checks if object is one of the move objects
'''
def isMovement(obj):
        return hasattr(obj, "Type") and (obj.Type == "Path" or obj.Type == "Move" or obj.Type == "Projection" or obj.Type == "Join")

'''
    Converts Part.Vertex to FreeCAD.Vector
    @param v - vertex to convert
    @returns FreeCAD.Vector
'''
def vertexToVector(v):
    return FreeCAD.Vector(v.X, v.Y, v.Z)

'''
    Converts FreeCAD.Vector to Part.Vertex
    @param v - point to convert
    @returns Part.Vertex
'''
def vectorToVertex(v):
    return Part.Vertex(v)
      
'''
  Get all selected Edges and Vertexes
'''
def getAllSelectedObjects(includeFace = False):
    objects = []
    for obj in  Gui.Selection.getSelectionEx():
        if obj.HasSubObjects:
            i = 0
            for subobj in obj.SubObjects:
                if issubclass(type(subobj), Part.Edge) or issubclass(type(subobj), Part.Vertex) or (includeFace and issubclass(type(subobj), Part.Face)):
                    objects.append((obj.Object, [obj.SubElementNames[i]]))
                i += 1
    return objects

def getEdgesLinks(obj, source):
    objects = []
    edges = source.Edges if issubclass(type(source), Part.Face) else source

    for fe in edges:
        for i, edge in enumerate(obj.Shape.Edges, start=1):
            if fe.isEqual(edge):
                objects.append([obj, ['Edge{}'.format(i)]])
            edge.reverse()
            if fe.isEqual(edge):
                objects.append([obj, ['Edge{}'.format(i)]])
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
    if issubclass(type(first), Part.Vertex) and issubclass(type(second), Part.Vertex):
        return True if distanceToVertex(first, second) < 0.01 else False
    return True if first.distanceToPoint(second) < 0.01 else False
  
'''
    Calculates distance between 2 vertexes in 3d space
    @param v1 - Vertex 1
    @param v2 - Vertex 2
'''
def distanceToVertex(v1, v2):
    return sqrt((v2.X - v1.X)**2 + (v2.Y - v1.Y)**2 + (v2.Z - v1.Z)**2) 

'''
  Synchronize direction of two edges using their end vertexes
  Sometimes it can produce wrong result (for example for heavy sweeped wing where tip leading edge past root trailing edge)
  Take it into account and check if reversing one set of vertexes produce shortest line when projecting to working planes
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
    edge  = Part.makeLine(v0, v1)

    # - Find point of intersection
    point = plane.Shape.Surface.intersect(edge.Curve)[0][0]
    # del edge
    return point

'''
    Get Config object by it's name
    @param config - Config object name
    @retuns Config
'''
def getConfigByName(config):
    if config is None or len(config) == 0:
        FreeCAD.Console.PrintError("Error: Config name is empty.\n")
        return
                
    configObj = FreeCAD.ActiveDocument.getObject(config)

    if configObj is None:
        FreeCAD.Console.PrintError("Error: Config not found.\n")
        return
    
    return configObj

'''
  Get working planes
'''
def getWorkingPlanes(group):
        if group is not None and group.Type == "Job":
            # - Initialize result
            result = []
            wpl = FreeCAD.ActiveDocument.getObject(group.WPLName)
            if wpl is not None:
                result.append(wpl)
            else:
                FreeCAD.Console.PrintError("ERROR:\n Left working plane not found.\n")
                return None
            wpr = FreeCAD.ActiveDocument.getObject(group.WPRName)
            if wpr is not None:
                result.append(wpr)
            else:
                FreeCAD.Console.PrintError("ERROR:\n Right working plane not found.\n")
            
            return result
        else:
            FreeCAD.Console.PrintError("ERROR:\n Parent Job not found.\n")

'''
  Make path on working planes by one or two sets of points
  @param first - First points set
  @param second - Second points set or None if projection is true
  @param planes - Array of planes
  @param projection - optional, if set to True, only first points set will be used and will be projected normal to WPs
  @return Array of points of intersection for each plane
'''
def makePathByPointSets(first, second, planes, projection = False):
    # - Point sets must contain same number of point
    if not projection and len(first) != len(second):
        return None

    # - Check working planes count
    if len(planes) == 0:
        return None

    # - Initialize result
    result = []
    
    if projection:
        for plane in planes:
            plane_points = []
            for point in first:
                plane_points.append(FreeCAD.Vector(plane.Position.x, point.y, point.z))
            result.append(plane_points)
    else: 
        pathsLength = []
        
        # try inverted edge only if we are working with edges, not with vertexes
        examineLength = len(first) > 1 and  len(second) > 1 and not projection

        # - Intersect line by each point pair and each plane
        for plane_index in range(len(planes)):
            plane_points = []
            for point_index in range(len(first)):            
                plane_points.append(
                    intersectLineAndPlane(first[point_index], second[point_index], planes[plane_index])
                )
            if examineLength:
                pathsLength.append(distanceToVertex(plane_points[START], plane_points[END]))        
            result.append([vertexToVector(point) for point in plane_points])

        # check with one edge reversed
        # if resulted length will be less then use this points order
        if(examineLength):
            resultInverted = []
            pathsLengthInverted = []
            # - Intersect line by each point pair and each plane
            for plane_index in range(len(planes)):
                plane_points = []
                for point_index in range(len(first)):            
                    plane_points.append(                
                        intersectLineAndPlane(first[point_index], second[len(second) - point_index - 1], planes[plane_index])
                    )
                pathsLengthInverted.append(distanceToVertex(plane_points[START], plane_points[END]))    
                resultInverted.append([vertexToVector(point) for point in plane_points])

            invert = True

            # if any edge from normal list shorter than same edge from inverted list - use normal list
            for pathIndex in range(len(pathsLength)):
                if pathsLength[pathIndex] < pathsLengthInverted[pathIndex]:
                    invert = False
                    break
            
            # - Done
            return (resultInverted if invert else result, invert)
    return (result, False)

'''
  Make path on working planes by two edges, vertices, or their combination
  @param first - First edge / vertex
  @param second - Second edge / vertex
  @param step - Distance between points in edge discretization
'''
def makePathPointsByEdgesPair(first, second, planes, step = 0.5, isStraitLine = False):    
    # - Find longest edge
    maxlen = first.Length if first.Length >= second.Length else second.Length

    # - Calculate number of discretization points
    points_count = int(float(maxlen) / float(step))

    if points_count < 2: #looks like edge too short and we can treat it as strait line
        points_count = 2
        isStraitLine = True

    #print("Point count = %d" % points_count)

    first_set   = []
    second_set  = []

    # - Discretize first edge
    if first.ShapeType == "Vertex":
        for i in range(points_count): first_set.append(first.Point)
    else:
        first_set = first.discretize(Number=points_count) if points_count > 2 and not isStraitLine else [first.firstVertex().Point, first.lastVertex().Point]

    # - Discretize second edge
    if second.ShapeType == "Vertex":
        for i in range(points_count): second_set.append(second.Point)
    else:
        second_set = second.discretize(Number=points_count) if points_count > 2 and not isStraitLine else [second.firstVertex().Point, second.lastVertex().Point]

    # - Make path
    (result, inverted) = makePathByPointSets(first_set, second_set, planes)
    return None if result is None else (result, inverted, points_count)

'''
  Make projected path on working planes by one edge or vertex
  @param first - First edge / vertex
  @param planes - working planes 
  @param step - Distance between points in edge discretization
'''
def makePathPointsByEdge(first, planes, step = 0.5, isStraitLine = False):    
    # - Detect vertex and vertex
    if first.ShapeType == "Vertex":
        return makePathByPointSets([first.Point], None, planes, True)

    # - Calculate number of discretization points
    points_count = int(float(first.Length) / float(step))
        
    #print("Point count = %d" % points_count)

    # - Discretize first edge
    first_set = first.discretize(Number=points_count) if points_count > 2 and not isStraitLine else [first.firstVertex().Point, first.lastVertex().Point]

    # - Make path
    (result, inverted) = makePathByPointSets(first_set, None,  planes, True)
    return None if result is None else (result, inverted, points_count)

'''
  Enumeration for the pick style
'''
REGULAR = 0
BOUNDBOX = 1
UNPICKABLE = 2

'''
  Get pick style node from view object
  @param viewprovider - view object
  @param create - optional. If set to True node will be added if not found
'''
def getPickStyleNode(viewprovider, create = True):
    from pivy import coin
    sa = coin.SoSearchAction()
    sa.setType(coin.SoPickStyle.getClassTypeId())
    sa.traverse(viewprovider.RootNode)
    if sa.isFound() and sa.getPath().getLength() == 1:
        return sa.getPath().getTail()
    else:
        if not create:
            return None
        node = coin.SoPickStyle()
        node.style.setValue(coin.SoPickStyle.SHAPE)
        viewprovider.RootNode.insertChild(node, 0)
        return node

'''
  Get pick style from view object
  @param viewprovider - view object
'''
def getPickStyle(viewprovider):
    node = getPickStyleNode(viewprovider, create = False)
    if node is not None:
        return node.style.getValue()
    else:
        return REGULAR

'''
  Set pick style
  @param viewprovider - view object
  @param style - pick style. Acceptable values: REGULAR, BOUNDBOX, UNPICKABLE
'''
def setPickStyle(viewprovider, style):
    node = getPickStyleNode(viewprovider, create = style != 0)
    if node is not None:
        return node.style.setValue(style)
    
def createRotationAxis(machine, config):
    if machine.getObject("RotationAxis") is None:
        RotationAxis = machine.newObject("Part::Line","RotationAxis")
        RotationAxis.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Helper"
        RotationAxis.X1 = 0
        RotationAxis.setExpression(".Y1", u"<<{}>>.OriginRotationX".format(config.Name))
        RotationAxis.Z1 = 0
        RotationAxis.X2 = 0
        RotationAxis.setExpression(".Y2", u"<<{}>>.OriginRotationX".format(config.Name))
        RotationAxis.setExpression(".Z2", u"<<{}>>.VerticalTravel + 50mm".format(config.Name))
        RotationAxis.Placement = App.Placement(App.Vector(0.00,0.00,0.00),App.Rotation(App.Vector(0.00,0.00,1.00),0.00))
        RotationAxis.ViewObject.PointSize = 0
        RotationAxis.ViewObject.Transparency = 70
        RotationAxis.ViewObject.LineColor = (1.0, 0.886, 0.023)
        RotationAxis.Label = "Rotation Axis"