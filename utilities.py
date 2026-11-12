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

FC_TYPES = ["Path", "Projection", "Rotation", "Enter", "Exit", "Move", "Join", "Route", "RouteClone", "Job", "Helper"]
FC_TYPES_TO_ROUTE = ["Path", "Projection", "Rotation", "Enter", "Exit", "Move", "Join"]

FC_KERF_DIRECTIONS = ["Normal", "None", "Reversed"]
FC_ROUTE_KERF_DIRECTIONS = ["Normal", "Reversed"]
FC_KERF_STRATEGY = ["None", "Uniform", "Dynamic"]
FC_TIME_UNITS = ["Seconds", "Milliseconds"]
FC_FEED_RATE_MODES = ["G94", "G93"]
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

    # - WorkingPlane value objects use an analytic constant-X intersection
    if hasattr(plane, "intersectLine"):
        return plane.intersectLine(v0, v1)

    # - Make line
    edge  = Part.makeLine(v0, v1)

    surface = plane.Shape.Surface if hasattr(plane, 'Shape') else plane.Surface
    
    # - Find point of intersection
    intersection = surface.intersect(edge.Curve)
    if len(intersection) == 0 or len(intersection[0]) == 0:
        raise Exception(f"Line ({v0.x}, {v0.y}, {v0.z}) - ({v1.x}, {v1.y}, {v1.z}) is parallel to the plane; no intersection")
    point = intersection[0][0]
    
    return App.Vector(point.X, point.Y, point.Z)

def getParallelEdgeLength(obj, planeX):
    '''
    Get length of edge projected to the parallel to working plane on specified X.
    
    Args:
        obj: Object containing the path and configuration
        planeX: X coordinate of the plane to project onto
    '''
    if not hasattr(obj, "Path_L") or not hasattr(obj, "Path_R") or not hasattr(obj, "EdgesInverted"):
        raise Exception(f"Unsupported object type {obj.Label}")

    job = obj.Document.getObject(obj.JobName)
    if job is None or job.Type != "Job":
        raise Exception(f"Active Job not found for {obj.Label}")

    left_points = obj.Path_L
    right_points = list(reversed(obj.Path_R)) if obj.EdgesInverted else obj.Path_R

    from MachinePlane import WorkingPlane
    plane = WorkingPlane.fromX(job, planeX)

    projected = []

    for l, r in zip(left_points, right_points):
        projected.append(intersectLineAndPlane(l, r, plane))

    # recalculate edges length
    path = Part.BSplineCurve()
    path.approximate(Points = projected, Continuity="C0")
    
    return float(path.length())

def getJob(obj):
    '''
    Get the Job object that owns obj.
    '''
    job = obj.Document.getObject(obj.JobName)
    if job is None or getattr(job, "Type", None) != "Job":
        raise Exception("ERROR: Active Job not found for {}.".format(obj.Label))
    return job


def bindJob(obj, job):
    '''
    Bind a child to its Job through a hidden link. Expressions use ._Job.Prop.
    This avoids the parent-group cycle and also works when the Job label
    contains spaces, which breaks hiddenref(<<Job>>.Prop) in FreeCAD.
    '''
    if not hasattr(obj, "_Job"):
        obj.addProperty("App::PropertyLinkHidden", "_Job", "", "", 5)
    obj._Job = job
    return job


def jobExpression(job, prop):
    '''
    Build a hidden expression reference from a child object to its Job.
    '''
    return u"._Job.{}".format(prop)


def getWorkingPlanes(group, doc):
    '''
    Get working plane snapshots derived from the Job configuration.
    @param group - Job object
    @param doc - FreeCAD document (kept for call-site compatibility)
    @returns list of WorkingPlane value objects
    '''
    if group is None or group.Type != "Job":
        FreeCAD.Console.PrintError("ERROR:\n Parent Job not found.\n")
        return None

    # - During document restore the Job may not have been migrated yet.
    #   Returning None lets proxies skip their execute pass; the migration
    #   touches the children so the next recompute runs them with real values.
    if not hasattr(group, "FieldWidth"):
        return None

    from MachinePlane import WorkingPlane
    return [
        WorkingPlane(group, LEFT),
        WorkingPlane(group, RIGHT),
    ]

def getPropertyExpression(obj, prop):
    '''
    Get the expression bound to an object property.
    @param obj - document object
    @param prop - property name
    @returns expression string or None when the property has no expression
    '''
    for path, expression in getattr(obj, "ExpressionEngine", []):
        if path.lstrip(".") == prop:
            return expression
    return None

def hasPropertyExpression(obj, prop):
    '''
    Check if an object property is driven by an expression.
    '''
    return getPropertyExpression(obj, prop) is not None

def overrideProperty(obj, prop, value):
    '''
    Detach a property from its expression and assign a literal value.
    @param obj - document object
    @param prop - property name
    @param value - new literal value
    '''
    if hasPropertyExpression(obj, prop):
        obj.clearExpression("." + prop)
    setattr(obj, prop, value)

def restorePropertyExpression(obj, prop, expression):
    '''
    Re-bind a property to an expression. Does nothing when expression is None.
    @param obj - document object
    @param prop - property name
    @param expression - expression string
    '''
    if expression:
        obj.setExpression("." + prop, expression)

def clearPropertyExpression(obj, prop):
    '''
    Remove an expression from a property, keeping its current value.
    '''
    if hasPropertyExpression(obj, prop):
        obj.clearExpression("." + prop)

def getPreferredValue(quantity):
    '''
    Convert a quantity to the user's preferred unit system.
    @param quantity - App.Units.Quantity
    @returns tuple (display_value, unit_string, factor_to_base)
    '''
    formatted, factor, unit = quantity.getUserPreferred()
    factor = float(factor)
    if factor == 0.0:
        factor = 1.0
    return float(quantity) / factor, unit, factor

def validateWorkingArea(points_L, points_R, wpl, wpr, tolerance=1e-7):
    '''
    Validate that route points stay inside the working plane boundaries.
    Checks Y (horizontal travel) and Z (vertical travel) extents of each
    point list against its working plane rectangle. X is fixed at the plane
    position by construction and is not checked. Raises an Exception on the
    first violation with a machine-term message. FreeCAD prefixes the object
    label when reporting the failure, so the message itself carries no label.
    @param points_L - left route point list (Offset_L)
    @param points_R - right route point list (Offset_R)
    @param wpl - left working plane object (Position, Length, Width)
    @param wpr - right working plane object (Position, Length, Width)
    @param tolerance - float noise absorption (not an intentional allowance)
    '''
    for points, plane, side in ((points_L, wpl, "left"), (points_R, wpr, "right")):
        if not points:
            continue
        # - Coerce to plain floats: real working planes return Quantity for
        #   Length/Width and float for Position, so mixed arithmetic would
        #   raise "Unit mismatch in plus operation".
        p_y = float(plane.Position.y)
        p_z = float(plane.Position.z)
        p_len = float(plane.Length)
        p_wid = float(plane.Width)
        ys = [p.y for p in points]
        zs = [p.z for p in points]
        if min(ys) < p_y - tolerance or max(ys) > p_y + p_len + tolerance:
            raise Exception(f"horizontal travel exceed machine boundary on a {side} plane. Adjust model position.")
        if min(zs) < p_z - tolerance or max(zs) > p_z + p_wid + tolerance:
            raise Exception(f"vertical travel exceed machine boundary on a {side} plane. Adjust model position.")

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
        return (None, False)

    # - Check working planes count
    if len(planes) != 2:
        return (None, False)

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
    if direction.Length > 1e-12:
        direction.normalize()
    
    perpendicular = direction.cross(App.Vector(1,0,0))
    if perpendicular.Length <= 1e-12:
        perpendicular = App.Vector(0,1,0) # direction is parallel to X axis (or degenerate) - offset along Y
    else:
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


def _joinMode(wire, point):
    '''
    Choose between trimming and extending a wire end to reach point.

    The point is an intersection of the supporting lines of the two wire
    ends, so it can lie alongside the wire rather than beyond its end.
    A point that projects onto a wire edge is inside the wire span and
    must be trimmed to; extending it would prepend/append a segment that
    reverses the wire direction and creates a cusp.  A point that projects
    onto a vertex is at/beyond an end and keeps the old extend behaviour.

    @param wire - wire to inspect
    @param point - candidate join point
    @return "trim" or "extend"
    '''
    vertex = Part.Vertex(point)
    (_, _, infos) = vertex.distToShape(wire)
    (_, _, _, topo, _, _) = infos[0]

    return "trim" if topo == "Edge" else "extend"


def intersectWires(wire1, wire2, tolerance = 1e-4, maxBridgeGap = 2.0):
    '''
    Check how wires intersect on a plane
    
    @param wire1 - first wire
    @param wire2 - second wire
    @param tolerance - distance under which wires are treated as touching
    @param maxBridgeGap - largest gap between the wire ends that is still
        joined by a straight bridging segment instead of being reported as an
        error (see the "bridge" case below). Defaults to 2 mm - well above a
        kerf-scale compensation step, well below a misplaced offset.

    @returns intersection of 2 wires as (intersection, wire1 mode, wire2 mode) where:
        - intersection is App.Vector() with coordinates of intersection
        - wire1 mode - mode of intersection for wire1: "none" | "trim" | "extend" | "replace"
        - wire2 mode - mode of intersection for wire2: "none" | "trim" | "extend" | "replace"

    Both modes "none" with a non-touching pair of wires means "bridge": the
    ends are too far apart for a meaningful intersection but close enough to
    connect with a straight segment, so neither wire is modified.  The caller
    that concatenates wires keeps the following wire's start point, so the
    previous segment is the one that absorbs the step.
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
                    
                    if dist <= maxBridgeGap:
                        # Adjacent offsets may have different magnitudes (dynamic
                        # kerf compensation scales the offset per edge), so they
                        # miss each other by a kerf-scale gap.  The intersection
                        # of their supporting lines then lies far beyond the far
                        # end of the examined wire: trimming/extending to it
                        # would reverse that wire instead of joining the ends.
                        # Bridge the ends with a straight segment instead.  Both
                        # wires keep their own offset and the caller drops the
                        # first wire's end point, so the previous (lead-in) edge
                        # absorbs the compensation step and the following cut
                        # edge starts exactly on its own offset.
                        if not SUPPRESS_WARNINGS:
                            App.Console.PrintWarning(
                                "Offset ends miss each other by {:.3f} mm and their "
                                "intersection lies outside the wires. Bridging them "
                                "with a straight segment.\n".format(dist))
                        intPoint = v1.add(v2).multiply(0.5)
                        return (intPoint, "none", "none")

                    raise Exception(f"Intersection is outside of the acceptable range.\n Initial distance check: {dist}, {vectors}, {infos}\n  {distance}, {infos[0]}")
                else:
                    # The point is not on the examined wire.  It may lie
                    # alongside it (adjacent offsets of different magnitude
                    # miss each other).  Classify each end independently:
                    # extending a point that is already alongside the wire
                    # would reverse the wire and create a cusp.
                    return (intPoint,
                            _joinMode(wire1, intPoint),
                            _joinMode(wire2, intPoint))

def _pointSegmentDistanceSq(point, a, b):
    '''
    Squared distance from point to segment [a, b].
    '''
    ab = b.sub(a)
    length_sq = ab.Length * ab.Length
    if length_sq == 0.0:
        d = point.sub(a)
        return d.Length * d.Length

    t = ((point.x - a.x) * ab.x + (point.y - a.y) * ab.y + (point.z - a.z) * ab.z) / length_sq
    t = max(0.0, min(1.0, t))

    px = a.x + t * ab.x
    py = a.y + t * ab.y
    pz = a.z + t * ab.z

    dx = point.x - px
    dy = point.y - py
    dz = point.z - pz
    return dx * dx + dy * dy + dz * dz


def findTrimEdgeIndex(wire, point, tolerance=1e-4):
    '''
    Find index of the edge in wire where point is located.

    Uses fast point-to-segment scan; falls back to OCC distToShape
    when the point is not on the wire within tolerance.

    Tie-break: for points within tolerance of a shared vertex the strict
    '<' scan returns the lower edge index, which yields identical trim
    output to the OCC distToShape choice.
    The fast scan measures distance to vertex-to-vertex chords, valid for
    the straight-segment polylines this function is used on; points
    deviating > tolerance from the wire fall back to OCC distToShape.
    '''
    verts = wire.Vertexes
    best_idx = -1
    best_dist_sq = float("inf")
    for i in range(len(verts) - 1):
        d = _pointSegmentDistanceSq(point, verts[i].Point, verts[i + 1].Point)
        if d < best_dist_sq:
            best_dist_sq = d
            best_idx = i

    if best_idx >= 0 and best_dist_sq <= tolerance * tolerance:
        return best_idx

    vertex = Part.Vertex(point)
    (_, _, infos) = vertex.distToShape(wire)
    (_, _, _, topo2, index2, _) = infos[0]
    if topo2 != "Edge":
        raise Exception("Trim expected intersection on edge.")
    return index2


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
        index = findTrimEdgeIndex(wire, point)
        if side == "start":
            return trimWireStart(wire, index, point)
        else:
            return trimWireEnd(wire, index, point)
        
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
    all_edges = wire.Edges
    # no edges to trim - create new one from wire start point and point of intersection
    if index == 0:
        return Part.Wire(Part.LineSegment(all_edges[0].firstVertex().Point, point).toShape())
    
    edges = [all_edges[edge] for edge in range(0, index)]
    if not all_edges[index - 1].lastVertex().Point.isEqual(point, 1e-7):
        edges.append(Part.LineSegment(all_edges[index - 1].lastVertex().Point, point).toShape())
    return Part.Wire(edges)

def trimWireStart(wire, index, point):
    '''
    trim wire at specified point from the start
    @param wire - wire to trim
    @param index - index of the edge where point lay
    @param point - coordinates of trim point
    @return new wire, where point is it's first vertex
    '''
    all_edges = wire.Edges
    # last segment, create new one        
    if index == len(all_edges) - 1:
        return Part.Wire(Part.LineSegment(point, all_edges[-1].lastVertex().Point).toShape())

    edges = [all_edges[edge] for edge in range(index + 1, len(all_edges))]
    if not point.isEqual(all_edges[index].lastVertex().Point, 1e-7):
        edges.insert(0, Part.LineSegment(point, all_edges[index].lastVertex().Point).toShape())
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
    if view_object is None:
        return
    node = getPickStyleNode(view_object, create = style != 0)
    if node is not None:
        return node.style.setValue(style)
    