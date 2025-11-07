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
FC_COMMENT_STYLES = ["; Comment", "(Comment)", "Ignore"]

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

SUPPRESS_WARNINGS = getParameterBool("SuppressWarnings", True)

def isNewStateHandling():
    '''
    Checks if we need handle object state in a new fashion
    It was first introduced in FC v.0.21.2 and was merged into LinkStage3 branch v.2024.113
    '''
    version = FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]+FreeCAD.Version()[2]
    return (version >= '0.212' and version < '2024.1130') or version >= '2024.1130'

def isStraitLine(wire):
    '''
    Checks if edge is strait line
    @param wire - wire to inspect
    '''
    if len(wire.Vertexes) == 2:
        len1 = (wire.Vertexes[0].Point - wire.Vertexes[1].Point).Length
        return isclose(abs(len1), wire.Length, rel_tol=1e-7)    
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
    @param plane - Plane
    @returns App.Vector Point of intersection
    '''
    # - Check is same points and move one of them along X axis to make able to make a line
    if (v0.isEqual(v1, 0.01)):
        v1.x += 1

    # - Make line
    edge  = Part.makeLine(v0, v1)

    surface = plane.Shape.Surface if hasattr(plane, 'Shape') else plane.Surface
    
    # - Find point of intersection
    point = surface.intersect(edge.Curve)[0][0]
    
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
    points_count = int(float(maxlen) / float(step)) if not isStraitLine else 2

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

def makeWire(points):
    ''' 
    Create wire from list of points

    @param points - list of points
    '''
    edges = []
    for i in range(len(points) - 1):
        edges.append(Part.LineSegment(points[i], points[i+1]))

    return Part.Wire([edge.toShape() for edge in edges])

def makeLineOffsetByPoints(startPoint, endPoint, offset):
    '''
    Create offset wire
    
    @param startPoint - start point of the line
    @param endPoint - end point of the line
    @param offset - distance to offset, where: negative - offset to the left; 0 - no offset; positive - offset to the right.
    
    @return offset wire
    '''
    
    direction = endPoint - startPoint
    direction.normalize()
    
    perpendicular = direction.cross(App.Vector(1,0,0))
    perpendicular.normalize()
    
    res_start = startPoint + float(offset) * perpendicular
    res_end = endPoint + float(offset) * perpendicular
    
    return Part.Wire(Part.LineSegment(res_start, res_end).toShape())

def makeLineOffset(wire, offset):
    '''
    Create offset wire
    
    @param wire - source wire (should be strait line, only start and end vertices will be used)
    @param offset - distance to offset, where: negative - offset to the left; 0 - no offset; positive - offset to the right.
    
    @return offset wire
    '''
    start = wire.Vertexes[0].Point
    end = wire.Vertexes[-1].Point

    return makeLineOffsetByPoints(start, end, offset)

def intersectWires(wire1, wire2, tolerance = 1e-4):
    '''
    Check how wires intersect on a plane
    
    @param wire1 - first wire
    @param wire2 - first wire

    @returns intersection of 2 wires as (intersection, type) where:
        - intersection is App.Vector() with coordinates of intersection
        - type - type of inersection: 0 - connected in point, 1 - need extend edges, 2 - need trim edges
    '''

    (dist, vectors, infos) = wire1.distToShape(wire2)
    
    (topo1, index1, param1, topo2, index2, param2) = infos[0]
    (v1, v2) = vectors[0]
    
    if math.isclose(0.0, dist, abs_tol=tolerance) and topo1 == topo2 == "Vertex":
        # wires already connected in intersection point
        return (v1, 0)
    else:
        if topo1 == topo2 == "Edge":
            #wires intersect, so just use first point of intersection as result. 
            #If one wire has high curvature (is arc or circle, or even spline) we can get 2 or more points of intersection.
            return (v1, 2)
        else:
            # TODO: most likely need to check what edges to extend to the intersection point. 90% of time it will be last and first edges.
            # wires not intersect, so calculate intersection by using first wire last edge and second wire first edge
            #print("Closest distance between wires {}; {}".format(dist, infos))

            L1_end_idx = index1 if topo1 == "Edge" else (-1 if topo1 == "Vertex" and index1 > 0 else 0)
            L2_start_idx = index2 if topo2 == "Edge" else (-1 if topo2 == "Vertex" and index2 > 0 else 0)

            L1_end = wire1.Edges[L1_end_idx]
            L2_start = wire2.Edges[L2_start_idx]

            res = L1_end.Curve.intersectCC(L2_start.Curve)

            if len(res) == 0:
                # wires are parallel but endpoints close together within tolerance
                if math.isclose(0.0, dist, abs_tol=tolerance):                        
                    return (v1, 0)
                else:                                         
                    message = "Wires not intersect. Check offset direction. Distance between edges = {}".format(dist)
                    raise Exception(message)
            else:
                int_type = 2
                if topo1 == "Vertex" and topo2 == "Vertex":
                    intPoint = App.Vector(res[0].X, res[0].Y, res[0].Z)
                    int_type = 1
                else:
                    vertex = Part.Vertex(res[0].X, res[0].Y, res[0].Z)
                    if topo1 == "Vertex" and topo2 == "Edge":
                        edge = wire2.Edges[index2]
                        param = param2
                    else:
                        edge = wire1.Edges[index1]
                        param = param1

                    (distance, _, _) = vertex.distToShape(edge)
                    if math.isclose(0.0, distance, abs_tol=tolerance):
                        intPoint = vertex.Point
                    else:
                        lastParam = edge.LastParameter if edge.FirstParameter < edge.LastParameter else edge.FirstParameter
                        
                        newParam = edge.Curve.parameterAtDistance(dist, param)
                        if newParam > lastParam:
                            newParam = edge.Curve.parameterAtDistance(dist*-1, param)
                        intPoint = edge.Curve.value(newParam)

            return (intPoint, int_type)

def connectWires(o1_wire, o2_wire, intersection):
    '''
    Extend/Trim offsets wires to the point of intersection
    @param o1_wire - first offset wire
    @param o2_wire - second offset wire
    @param intersection - (point, type) - intersection point of 2 wires and it's type ->
    (0 - already connected; 2 - intersection on both wires; 1 - not intersect directly, or endpoint of one wire is on the edge of another)
    
    @returns pair of wires
    '''
    
    (point, tp) = intersection
    vertex = Part.Vertex(point)
    points = []
    
    if tp == 0:
        return [o1_wire, o2_wire]
    if tp == 1:
        # need to check if intersection is part of the line or not
        (dist1, vectors1, infos1) = vertex.distToShape(o1_wire)
        (dist2, vectors2, infos2) = vertex.distToShape(o2_wire)

        #print("Point to L1 offset: point on shape: {}; info: {}".format(vectors1[0][1], infos1[0]))
        #print("Point to L2 offset: point on shape: {}; info: {}".format(vectors2[0][1], infos2[0]))

        wire1 = None
        wire2 = None
        # check if intersection is on line or outside for L1 offset
        (topo1, index1, param1, topo2, index2, param2) = infos1[0]
        # intersection is outside. We need to add one more edge to offset
        if dist1 > 0 and topo2 == "Vertex": 
            points = [v.Point for v in o1_wire.Vertexes] + [point] 
            wire1 = makeWire(points)
        else:            
            wire1 = trimWireEnd(o1_wire, index2, point)
        
        (topo1, index1, param1, topo2, index2, param2) = infos2[0]
        # intersection is outside. We need to add one more edge to offset
        if dist2 > 0 and topo2 == "Vertex": 
            points = [point] + [v.Point for v in o2_wire.Vertexes]
            wire2 = makeWire(points)
        else:
            wire2 = trimWireStart(o2_wire, index2, point)
            
        return [wire1, wire2]
    if tp == 2:
        (dist, vectors, infos) = o1_wire.distToShape(o2_wire)
        (topo1, index1, param1, topo2, index2, param2) = infos[0]
                
        #trim first wire
        wire1 = trimWireEnd(o1_wire, index1, point)
        #trim second wire
        wire2 = trimWireStart(o2_wire, index2, point)
        return [wire1, wire2]
    return None
    
def trimWireEnd(wire, index, point):
    '''
    trim wire at specified point from the end
    @param wire - wire to trim
    @param index - index of the edge where point lay
    @param point - coordinates of trim point
    @return new wire, where point is it's last vertex
    '''
    # no edges to trim - create new one from wire start point and point of intersection
    if index == 0:
        return Part.Wire(Part.LineSegment(wire.Edges[0].firstVertex().Point, point).toShape())
    
    edges = [wire.Edges[edge] for edge in range(0, index)]
    if wire.Edges[index - 1].lastVertex().Point != point:
        edges.append(Part.LineSegment(wire.Edges[index - 1].lastVertex().Point, point).toShape())
    return Part.Wire(edges)
    
def trimWireStart(wire, index, point):
    '''
    trim wire at specified point from the start
    @param wire - wire to trim
    @param index - index of the edge where point lay
    @param point - coordinates of trim point
    @return new wire, where point is it's first vertex
    '''
    # last segment, create new one        
    if index == len(wire.Edges) - 1:
        Part.Wire(Part.LineSegment(point, wire.Edges[-1].lastVertex().Point).toShape())

    edges = [wire.Edges[edge] for edge in range(index + 1, len(wire.Edges))]
    if point != wire.Edges[index].lastVertex().Point:
        edges.insert(0, Part.LineSegment(point, wire.Edges[index].lastVertex().Point).toShape())
    return Part.Wire(edges)


def makeWireOffset(source, offset):
        '''
        Create offset wire
        @param source - source wire
        @param offset - distance to offset, where: negative - offset to the left; 0 - no offset; positive - offset to the right.
        
        @returns offset wire
        '''

        if offset == 0:
            return source
        
        if isStraitLine(source): # strait line     
            wire = makeLineOffset(source, offset)                
            return wire
        else:
            try:
                offset1 = source.makeOffset2D(offset,2, False, True, True)
                
                wire = Part.Wire(offset1.Edges) # we need it to have sorted edges, it will help to operate with edges in a future

                (_, _, infos)  = source.Vertexes[0].distToShape(wire)
                (_, idx1, _, _, idx2, _) = infos[0]
                if idx1 != idx2: #offset wire reversed, reverse edges
                    wire = Part.Wire(offset1.Edges[::-1])
            except Exception as ex:
                #print("Source points: {}".format([v.Point for v in source.Vertexes]))
                if not SUPPRESS_WARNINGS:
                    App.Console.PrintWarning("Unable to create offset using makeOffset2D. Fallback to my calculation.\n {}".format(ex))

                wires = []
                for edge in source.Edges:
                    wires.append(makeLineOffset(edge, offset))
                
                intersections = []
                for i in range(len(wires) - 1):                
                    intersections.append(intersectWires(wires[i], wires[i + 1]))

                points = []
                firstWire = None
                for i in range(len(wires) - 1):
                    if firstWire == None:
                        firstWire = wires[i]
                        
                    (first, second) = connectWires(firstWire, wires[i + 1], intersections[i])
                    
                    for vi in range(len(first.Vertexes) - 1):
                        points.append(first.Vertexes[vi].Point)
                        
                    firstWire = second

                if firstWire is None:
                    firstWire = wires[-1]
                
                for v in firstWire.Vertexes:
                        points.append(v.Point)
                wire = makeWire(points)

        return wire

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
    