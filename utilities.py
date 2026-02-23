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

def getParallelEdgeLength(obj, planeX):
    '''
    Get length of edge projected to the parallel to working plane on specified X.
    
    Args:
        obj: Object containing the path and configuration
        planeX: X coordinate of the plane to project onto
    '''
    if not hasattr(obj.Proxy, "getConfig") or not hasattr(obj, "Path_L") or not hasattr(obj, "Path_R") or not hasattr(obj, "EdgesInverted"):
        raise Exception(f"Unsupported object type {obj.Label}")

    config = obj.Proxy.getConfig(obj)
    left_points = obj.Path_L
    right_points = list(reversed(obj.Path_R)) if obj.EdgesInverted else obj.Path_R

    norm = App.Vector(1.0, 0.0, 0.0)
    xdir = App.Vector(0.0, 1.0, 0.0)
    plane = Part.makePlane(float(config.HorizontalTravel), float(config.VerticalTravel), App.Vector(planeX, float(-config.OriginX), 0), norm, xdir)

    projected = []

    for l, r in zip(left_points, right_points):
        projected.append(intersectLineAndPlane(l, r, plane))

    # recalculate edges length
    path = Part.BSplineCurve()
    path.approximate(Points = projected, Continuity="C0")
    
    return float(path.length())

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

def makePathPointsByEdgesOrVerticesPair(first, second, planes, step = 0.5, isStraitLine = False):    
    '''
    Make path on working planes by two edges or vertices

    @param first - First edge / vertex
    @param second - Second edge / vertex
    @param step (optional) - Distance between points in edge discretization. 0.5 by default
    @param isStraitLine (optional) - Indicate that both edges is stait lines, so we do not need to discretize em. False by default
    @returns tuple (result, inverted, points_count), where:
        result - set of resulted points; 
        inverted - indicate that edge was inverted;
        points_count - count of vertices after descretization with set step
    '''
    if first.ShapeType != second.ShapeType:
        raise Exception(f"Invalid path: cannot combine {first.ShapeType} with {second.ShapeType}. "
            "Select two edges or two vertices."
        )
    
    if first.ShapeType == "Vertex" and second.ShapeType == "Vertex":
        (result, inverted) = makePathByPointSets([first.Point], [second.Point], planes)
        return (result, False, 1)
    
    step = max(float(step), 1e-2) # avoid too much points for short edges

    # - Calculate number of discretization points
    points_count = int(math.ceil(float(max(first.Length, second.Length)) / float(step)))

    if points_count < 2: #looks like edge too short and we can treat it as strait line
        isStraitLine = True

    first_set   = []
    second_set  = []

    if isStraitLine:
        first_set = [first.firstVertex().Point, first.lastVertex().Point]
        second_set = [second.firstVertex().Point, second.lastVertex().Point]
        points_count = 2
    else:        
        # - Discretize edges
        first_set = first.discretize(Number=points_count)
        second_set = second.discretize(Number=points_count)

    # - Make path
    (result, inverted) = makePathByPointSets(first_set, second_set, planes)
    return (result, inverted, points_count)

def makePathPointsByEdgeOrVertex(first, planes, step = 0.5, isStraitLine = False):    
    '''
    Make projected path on working planes by one edge or vertex

    @param first - First edge / vertex
    @param planes - working planes 
    @param step (optional) - Distance between points in edge discretization. 0.5 by default
    @param isStraitLine (optional) - Indicate that edge is stait line, so we do not need to discretize. False by default
    @returns tuple (result, inverted, points_count), where:
        result - set of resulted points; 
        inverted - indicate that edge was inverted;
        points_count - count of vertices after descretization with set step
    '''
    # - Detect vertex and vertex
    if first.ShapeType == "Vertex":
        (result, _) = makePathByPointSets([first.Point], None, planes, True)
        return (result, False, 1)

    step = max(float(step), 1e-2) # avoid too much points for short edges

    # - Calculate number of discretization points
    points_count = int(math.ceil(float(first.Length) / float(step)))
    if points_count < 2: #looks like edge too short and we can treat it as strait line
        isStraitLine = True

    if isStraitLine:
        first_set = [first.firstVertex().Point, first.lastVertex().Point]
        points_count = 2
    else:        
        # - Discretize edge
        first_set = first.discretize(Number=points_count)

    # - Make path
    (result, _) = makePathByPointSets(first_set, None,  planes, True)
    return (result, False, points_count)

def makeWire(points):
    ''' 
    Create wire from list of points

    @param points - list of points
    '''
    if len(points) < 2:
        return None
    
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
    @param wire2 - second wire

    @returns intersection of 2 wires as (intersection, wire1 mode, wire2 mode) where:
        - intersection is App.Vector() with coordinates of intersection
        - wire1 mode - mode of intersection for wire1: "none" | "trim" | "extend" | "replace"
        - wire2 mode - mode of intersection for wire2: "none" | "trim" | "extend" | "replace"
    '''
    if wire1 is None and wire2 is None:
        raise Exception("At least one wire should be present")

    # first wire is missing or single point
    if wire1 is None and wire2 is not None:
        return (wire2.Vertexes[0].Point, "none", "none")
    # second wire is missing or single point
    if wire2 is None and wire1 is not None:
        return (wire1.Vertexes[-1].Point, "none", "none")
    
    # check if wires already intersect or close enough to be treated as intersected    
    (dist, vectors, infos) = wire1.distToShape(wire2)
    
    (topo1, index1, param1, topo2, index2, param2) = infos[0]
    (v1, v2) = vectors[0]
    
    
    # wires are intersecting or close enough to be treated as intersecting
    # we can just use point of intersection as result
    if math.isclose(0.0, dist, abs_tol=tolerance): 
        # wires already connected in intersection point or close enough to be treated as connected
        if topo1 == topo2 == "Vertex":       
            return (v1, "none", "none")
        #wires intersect, so just use first point of intersection as result. 
        #If one wire has high curvature (is arc or circle, or even spline) we can get 2 or more points of intersection.
        if topo1 == topo2 == "Edge":           
            return (v1, "trim", "trim")
        elif topo1 == "Vertex" and topo2 == "Edge":
            # one wire edge is connected to another wire vertex. 
            # need to trim edge to the vertex
            return (v1, "none", "trim")
        elif topo1 == "Edge" and topo2 == "Vertex":
            # one wire edge is connected to another wire vertex. 
            # need to trim edge to the vertex
            return (v1, "trim", "none")
        
    # wire are not intersecting directly
    # need to check if it's possible to connect them safely
    else:          
        # wires not intersect, so calculate intersection by using first wire last edge and second wire first edge
        
        # edge cases when intersection point on a wrong side of the edge
        # we only can extend first edge forward and thim second edge backward
        if topo1 == "Vertex" and topo2 == "Edge" and index1 == 0:
            raise Exception(f"Intersection is outside of the acceptable range. {dist}, {vectors}, {infos}")
        if topo2 == "Vertex" and topo1 == "Edge" and index2 != 0:
            raise Exception(f"Intersection is outside of the acceptable range. {dist}, {vectors}, {infos}")

        # find a wire to examine
        if topo1 == "Vertex":
            wire = wire2
            idx = 0
            isFirst = False
        else:
            wire = wire1
            idx = len(wire1.Vertexes) - 1
            isFirst = True

        # get edges indices to calculate intersection point
        L1_end_idx = index1 if topo1 == "Edge" else (-1 if topo1 == "Vertex" and index1 > 0 else 0)
        L2_start_idx = index2 if topo2 == "Edge" else (-1 if topo2 == "Vertex" and index2 > 0 else 0)

        # get edges to calculate intersection point
        L1_end = wire1.Edges[L1_end_idx]
        L2_start = wire2.Edges[L2_start_idx]

        # the max distance between end points we can safelly split to introduce virtual intersection point
        maxDistanceToSplit = (L1_end.Length + L2_start.Length)

        # direction from start to end
        dir1 = L1_end.lastVertex().Point.sub(L1_end.firstVertex().Point)
        dir2 = L2_start.lastVertex().Point.sub(L2_start.firstVertex().Point)

        angle = math.degrees(dir1.getAngle(dir2))
        angle_tolerance = 2.0 # if angle between edges less than this value, we can treat lines as they are parallel
        # print(f"Angle between edges: {math.degrees(dir1.getAngle(dir2))}")

        # calculate intersection point of 2 edges
        res = L1_end.Curve.intersectCC(L2_start.Curve)

        if len(res) == 0:
            # wires are parallel
            # but if endpoints are in a right order and close enough we can add point between them
            if topo1 == "Vertex" and topo2 == "Vertex" and index1 > index2 and dist <= maxDistanceToSplit:
                intPoint = v1.add(v2).multiply(0.5) # use middle point between 2 vertices as intersection
                return (intPoint, "replace", "replace") # special case when both wires are nearly parallel -> endpoints will be replaced with a virtual intersection
            else:
                raise Exception(f"Wires not intersect. Check offset direction. {dist}, {vectors}, {infos}")
        else:
            intPoint = App.Vector(res[0].X, res[0].Y, res[0].Z)
            vertex = Part.Vertex(intPoint)

            (distance, _, infos) = vertex.distToShape(wire)
            (_, _, _, topo, index, _) = infos[0]

            # intersection point is on wire, so we can just trim edge to this point
            # or it's close to the vertex, but still outside of the wire - then we need to extend edge to this point
            if math.isclose(0.0, distance, abs_tol=tolerance):
                if topo == "Vertex":
                    return (intPoint, "extend", "extend")
                else:
                    return (intPoint, "trim", "extend") if isFirst else (intPoint, "extend", "trim")
            # intersection point is outside of wire
            # we can decide on adding virtual intersection when angle between edges is small and distance is small too
            elif (angle < angle_tolerance or angle > 360 - angle_tolerance) and dist <= maxDistanceToSplit:                
                intPoint = v1.add(v2).multiply(0.5) # use middle point between 2 vertices as intersection
                return (intPoint, "replace", "replace") # special case when both wires are nearly parallel
            # intersection point is outside of wire
            # we probably can extend edge to this point or wire may be consumed
            else:                
                if topo == "Vertex" and index != idx:
                    # wires are nearly parallel and intersection point is outside of wire
                    # so we cannot connect them without consuming one of wires
                    # but if endpoints are in a right order and close enough we can add point between them
                    if topo1 == "Vertex" and topo2 == "Vertex" and index >= idx and dist <= maxDistanceToSplit:
                        intPoint = v1.add(v2).multiply(0.5) # use middle point between 2 vertices as intersection
                        return (intPoint, "replace", "replace") # special case when both wires are nearly parallel
                    
                    else:
                        v = Part.show(vertex, "Wrong Intersection Point") # debug point of wrong intersection
                        v.ViewObject.PointSize = 6
                        Part.show(L1_end, "Wrong Intersection Edge") # debug edge to which wrong intersection point belongs
                        Part.show(L2_start, "Wrong Intersection Edge") # debug edge to which wrong intersection

                        raise Exception(f"Intersection is outside of the acceptable range.\n Initial distance check: {dist}, {vectors}, {infos}\n  {distance}, {infos[0]}")
                else:
                    return (intPoint, "extend", "extend")

def trimOrExtendWire(wire, point, mode, side):
    '''
    Extend/Trim wire to the point of intersection
    
    :param wire: Wire to fix
    :param point: Intersection point
    :param mode: Mode of operation ("none" | "trim" | "extend" | "replace")
    :param side: Side of the wire to operate on ("start" | "end")
    '''

    if mode == "none":
        return wire
    elif mode == "trim":
        vertex = Part.Vertex(point)
        (_, _, infos) = vertex.distToShape(wire)
        (_, _, _, topo2, index2, _) = infos[0]

        if topo2 != "Edge":            
            raise Exception("Trim expected intersection on edge.")
    
        if side == "start":
            return trimWireStart(wire, index2, point)
        else:
            return trimWireEnd(wire, index2, point)
        
    elif mode == "extend":
        if side == "start":
            if not isCommonPoint(point, wire.Vertexes[0], tolerance=1e-6):
                points = [point] + [v.Point for v in wire.Vertexes]
                return makeWire(points)
        else:
            if not isCommonPoint(point, wire.Vertexes[-1], tolerance=1e-6):
                points = [v.Point for v in wire.Vertexes] + [point]
                return makeWire(points)
        return wire
        
    elif mode == "replace":
        points = [v.Point for v in wire.Vertexes]
        if side == "start":
            points[0] = point
        else:
            points[-1] = point
        return makeWire(points)

def connectWires(o1_wire, o2_wire, intersection):
    '''
    Extend/Trim offsets wires to the point of intersection
    @param o1_wire - first offset wire
    @param o2_wire - second offset wire
    @param intersection - (point, wire1_mode, wire2_mode) - intersection point of 2 wires and what to do with it ->
    ("none" | "trim" | "extend" | "replace")
    
    @returns pair of wires
    '''
    
    (point, wire1_mode, wire2_mode) = intersection
    
    # Part.show(Part.Vertex(point), "Intersection Point") # debug point of intersection
    return [trimOrExtendWire(o1_wire, point, wire1_mode, "end"), trimOrExtendWire(o2_wire, point, wire2_mode, "start")]

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
        return Part.Wire(Part.LineSegment(point, wire.Edges[-1].lastVertex().Point).toShape())

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
    