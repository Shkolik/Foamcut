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
import math
from math import isclose

DEFAULT_CONFIG_PATH = "User parameter:BaseApp/Workbench/FoamcutWB/DefaultMachineConfig"

START       = 0           # - Segment start point index
END         = -1          # - Segment end point index

LEFT = -1
RIGHT = 1

FC_TYPES = ["Path", "Projection", "Rotation", "Enter", "Exit", "Move", "Join", "Route", "Job", "Helper"]
FC_TYPES_TO_ROUTE = ["Path", "Projection", "Rotation", "Enter", "Exit", "Move", "Join"]

FC_KERF_DIRECTIONS = ["Normal", "None", "Reversed"]
FC_ROUTE_KERF_DIRECTIONS = ["Normal", "Reversed"]
FC_KERF_STRATEGY = ["None", "Uniform", "Dynamic"]
FC_TIME_UNITS = ["Seconds", "Milliseconds"]

def get_module_path():
    '''
    Returns the current module path.
    Determines where this file is running from, so works regardless of whether
    the module is installed in the app's module directory or the user's app data folder.
    (The second overrides the first.)
    '''
    return os.path.dirname(__file__)

def getResourcesPath():
    '''
    Returns the resources path.
    '''
    return os.path.join(get_module_path(), "Resources")

def getIconPath(icon: str):
    '''
    Returns the icon path.
    @param icon - icon file name
    '''
    return os.path.join(getResourcesPath(), "icons", icon)

def getParameterFloat(name, default):
    parameters = App.ParamGet(DEFAULT_CONFIG_PATH)
    floats = parameters.GetFloats()
    if name not in floats:
        parameters.SetFloat(name, default)
    
    return parameters.GetFloat(name)

def getParameterInt(name, default):
    parameters = App.ParamGet(DEFAULT_CONFIG_PATH)
    ints = parameters.GetInts()
    if name not in ints:
        parameters.SetInt(name, default)
    
    return parameters.GetInt(name)

def getParameterBool(name, default):
    parameters = App.ParamGet(DEFAULT_CONFIG_PATH)
    bools = parameters.GetBools()
    if name not in bools:
        parameters.SetBool(name, default)
    
    return parameters.GetBool(name)

def getParameterString(name, default):
    parameters = App.ParamGet(DEFAULT_CONFIG_PATH)
    strings = parameters.GetStrings()
    if name not in strings:
        parameters.SetString(name, default)
    
    return parameters.GetString(name)

def isNewStateHandling():
    '''
    Checks if we need handle object state in a new fashion
    It was first introduced in FC v.0.21.2 and was merged into LinkStage3 branch v.2024.113
    '''
    version = FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]+FreeCAD.Version()[2]
    return (version >= '0.212' and version < '2024.1130') or version >= '2024.1130'

def isStraitLine(edge):
    '''
    Checks if edge is strait line
    @param edge - edge to inspect
    '''
    if len(edge.Vertexes) == 2:
        len1 = (edge.Vertexes[0].Point - edge.Vertexes[1].Point).Length
        return isclose(abs(len1), edge.Length, rel_tol=1e-7)    
    else:
        return False

def isMovement(obj):
    '''
    Checks if object is one of the move objects
    @param obj - object to inspect
    '''
    return hasattr(obj, "Type") and (obj.Type == "Path" or obj.Type == "Move" or obj.Type == "Projection" or obj.Type == "Join")

def getAllSelectedObjects(includeFace = False):
    '''
    Get all selected sub ofjects like Edges and Vertexes
    @param includeFace (optional) - include selected faces to result. False by default
    '''
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
    '''
    Get list of sub object links
    @param obj - App.DocumentObject - parent object
    @param source - source for list of edges. Could be Part.Face or list of edges
    @returns list of tuple (obj, ["<EdgeName>"]) 
    '''
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
    
def getAllSelectedEdges():
    '''
    Get all selected Edges in format of sub object links
    @returns list of tuple (parentObject, ["<EdgeName>"]) 
    '''
    objects = []
    for obj in  Gui.Selection.getSelectionEx():
        if obj.HasSubObjects:
            i = 0
            for subobj in obj.SubObjects:
                if issubclass(type(subobj), Part.Edge):
                    objects.append((obj.Object, [obj.SubElementNames[i]]))
                i += 1
    return objects

def canMergeToBSpline(first, second, angleTolerance = 5.0):
    """
    Check if 2 edges could be merged into 1 bspline 

    @param first - first edge
    @param second - second edge
    @param angleTolerance (optional) - minimum angle between 2 edges. 5.0 degrees by default

    @returns True if angle between 2 edges less than tolerance
    """
    dir1 = first.Vertexes[0].Point.sub(first.Vertexes[1].Point)
    dir2 = second.Vertexes[0].Point.sub(second.Vertexes[1].Point)
    angle = math.degrees(dir2.getAngle(dir1))

    return angle < angleTolerance

def isCommonPoint(first, second, tolerance = 0.01):
    '''
    Check if points are common
    @param first - Fist point
    @param second - Second point
    @param tolerance (optional) - tolerance used in comparison. By default 0.01
    @returns True if point are common
    '''
    firstPoint = first.Point if issubclass(type(first), Part.Vertex) else first
    secondPoint = second.Point if issubclass(type(second), Part.Vertex) else second

    return firstPoint.distanceToPoint(secondPoint) < tolerance

def intersectLineAndPlane(v0, v1, plane):
    '''
    Find point of intersection of line and plane
    @param v0 - Fist line point
    @param v1 - Second line point
    @returns App.Vector Point of intersection
    '''
    # - Check is same points and move one of them along X axis to make able to make a line
    if (v0.isEqual(v1, 0.01)):
        v1.x += 1

    # - Make line
    edge  = Part.makeLine(v0, v1)

    # - Find point of intersection
    point = plane.Shape.Surface.intersect(edge.Curve)[0][0]
    
    return App.Vector(point.X, point.Y, point.Z)

def getConfigByName(config, doc):
    '''
    Get Config object by it's name

    @param config - Config object name
    @param doc - FreeCAD document
    @returns Config
    '''

    if config is None or len(config) == 0:
        FreeCAD.Console.PrintError("Error: Config name is empty.\n")
        return
                
    configObj = doc.getObject(config)

    if configObj is None:
        FreeCAD.Console.PrintError("Error: Config not found.\n")
        return
    
    return configObj

def getWorkingPlanes(group, doc):
    '''
    Get working planes
    @param group - Job object
    @param doc - FreeCAD document
    @returns list of working planes
    '''
    if group is not None and group.Type == "Job":
        # - Initialize result
        result = []
        wpl = doc.getObject(group.WPLName)
        if wpl is not None:
            result.append(wpl)
        else:
            FreeCAD.Console.PrintError("ERROR:\n Left working plane not found.\n")
            return None
        wpr = doc.getObject(group.WPRName)
        if wpr is not None:
            result.append(wpr)
        else:
            FreeCAD.Console.PrintError("ERROR:\n Right working plane not found.\n")
        
        return result
    else:
        FreeCAD.Console.PrintError("ERROR:\n Parent Job not found.\n")

def makePathByPointSets(first, second, planes, projection = False):
    '''
    Make path on working planes by one or two sets of points

    @param first - First points set
    @param second - Second points set or None if projection is true
    @param planes - list of planes
    @param projection - optional, if set to True, only first points set will be used and will be projected normal to WPs
    @return list of points of intersection for each plane
    '''
    # - Point sets must contain same number of point
    if not projection and len(first) != len(second):
        return None

    # - Check working planes count
    if len(planes) != 2:
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
        
        # try inverted edge only if we are working with edges, not with vertices
        examineLength = len(first) > 1 and  len(second) > 1 and not projection

        # - Intersect line by each point pair and each plane
        for plane_index in range(len(planes)):
            plane_points = []
            for point_index in range(len(first)):            
                plane_points.append(
                    intersectLineAndPlane(first[point_index], second[point_index], planes[plane_index])
                )
            if examineLength:
                pathsLength.append(plane_points[START].distanceToPoint(plane_points[END]))        
            result.append(plane_points)

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
                pathsLengthInverted.append(plane_points[START].distanceToPoint(plane_points[END]))    
                resultInverted.append(plane_points)

            invert = True

            # if any edge from normal list shorter than same edge from inverted list - use normal list
            for pathIndex in range(len(pathsLength)):
                if pathsLength[pathIndex] < pathsLengthInverted[pathIndex]:
                    invert = False
                    break
            
            # - Done
            return (resultInverted if invert else result, invert)
    return (result, False)

def makePathPointsByEdgesPair(first, second, planes, step = 0.5, isStraitLine = False):    
    '''
    Make path on working planes by two edges, vertices, or their combination

    @param first - First edge / vertex
    @param second - Second edge / vertex
    @param step (optional) - Distance between points in edge discretization. 0.5 by default
    @param isStraitLine (optional) - Indicate that both edges is stait lines, so we do not need to discretize em. False by default
    @returns tuple (result, inverted, points_count), where:
        result - set of resulted points; 
        inverted - indicate that edge was inverted;
        points_count - cout of vertices after descretization with set step
    '''
    # - Find longest edge
    maxlen = first.Length if first.Length >= second.Length else second.Length

    # - Calculate number of discretization points
    points_count = int(float(maxlen) / float(step))

    if points_count < 2: #looks like edge too short and we can treat it as strait line
        points_count = 2
        isStraitLine = True

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

def makePathPointsByEdge(first, planes, step = 0.5, isStraitLine = False):    
    '''
    Make projected path on working planes by one edge or vertex

    @param first - First edge / vertex
    @param planes - working planes 
    @param step (optional) - Distance between points in edge discretization. 0.5 by default
    @param isStraitLine (optional) - Indicate that edge is stait line, so we do not need to discretize. False by default
    @returns tuple (result, inverted, points_count), where:
        result - set of resulted points; 
        inverted - indicate that edge was inverted;
        points_count - cout of vertices after descretization with set step
    '''
    # - Detect vertex and vertex
    if first.ShapeType == "Vertex":
        return makePathByPointSets([first.Point], None, planes, True)

    # - Calculate number of discretization points
    points_count = int(float(first.Length) / float(step))
    if points_count < 2: #looks like edge too short and we can treat it as strait line
        points_count = 2
        
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

def getPickStyleNode(view_object, create = True):
    '''
    Get pick style node from view object
    @param view_object - view object
    @param create (optional) - If set to True node will be added if not found. True by default.
    '''
    from pivy import coin
    sa = coin.SoSearchAction()
    sa.setType(coin.SoPickStyle.getClassTypeId())
    sa.traverse(view_object.RootNode)
    if sa.isFound() and sa.getPath().getLength() == 1:
        return sa.getPath().getTail()
    else:
        if not create:
            return None
        node = coin.SoPickStyle()
        node.style.setValue(coin.SoPickStyle.SHAPE)
        view_object.RootNode.insertChild(node, 0)
        return node

def getPickStyle(view_object):
    '''
    Get pick style from view object
    @param view_object - view object
    '''
    node = getPickStyleNode(view_object, create = False)
    if node is not None:
        return node.style.getValue()
    else:
        return REGULAR

def setPickStyle(view_object, style):
    '''
    Set pick style
    @param view_object - view object
    @param style - pick style. Acceptable values: REGULAR, BOUNDBOX, UNPICKABLE
    '''
    node = getPickStyleNode(view_object, create = style != 0)
    if node is not None:
        return node.style.setValue(style)
    