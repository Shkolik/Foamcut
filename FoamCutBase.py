# -*- coding: utf-8 -*-

__title__ = "Base classes"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
from utilities import *

# - Distance from a selected path point to the wire line that owns it. The path
#   point is the exact intersection of that line with the working plane, so this
#   only absorbs discretization noise.
WIRE_LINE_TOLERANCE = 0.1

def getRoutesForObject(obj):
    '''
    Return the routes that use a movement object.
    @param obj - movement object
    @returns list of Route objects
    '''
    doc = getattr(obj, "Document", None)
    if doc is None:
        return []
    return [route for route in doc.Objects
            if getattr(route, "Type", None) == "Route" and obj in route.Objects]

def recomputeRoutesForObject(obj):
    '''
    Recompute every route that uses a movement object.
    @param obj - movement object
    @returns list of recomputed Route objects
    '''
    routes = getRoutesForObject(obj)
    for route in routes:
        route.touch()
        route.recompute()
    return routes

class FoamCutBaseObject:
    """FoamCut base object"""

    def __init__(self, obj, jobName):
        obj.addProperty("App::PropertyString",    "Type", "", "", 5)
        obj.addProperty("App::PropertyString",    "JobName", "", "", 5).JobName = jobName

        if hasattr(obj, "Placement"):
            obj.setEditorMode("Placement", 3)

    def getEdges(self, obj):
        left = None
        right = None

        if hasattr(obj, "LeftEdge") and obj.LeftEdge is not None:
            left = obj.LeftEdge[0].getSubObject(obj.LeftEdge[1][0])
        elif hasattr(obj, "Source") and obj.Source is not None:
            left = obj.Source[0].getSubObject(obj.Source[1][0])
        elif hasattr(obj, "LeftEdgeName") and obj.LeftEdgeName:
            left = obj.getSubObject(obj.LeftEdgeName)

        if hasattr(obj, "RightEdge") and obj.RightEdge is not None:
            right = obj.RightEdge[0].getSubObject(obj.RightEdge[1][0])
        elif hasattr(obj, "Source") and obj.Source is not None:
            right = obj.Source[0].getSubObject(obj.Source[1][0])
        elif hasattr(obj, "RightEdgeName") and obj.RightEdgeName:
            right = obj.getSubObject(obj.RightEdgeName)

        return (left, right if right is not None else left)

class FoamCutMovementBaseObject(FoamCutBaseObject):
    def __init__(self, obj, jobName):
        super().__init__(obj, jobName)  

        job = getJob(obj)
        bindJob(obj, job)

        obj.addProperty("App::PropertyVectorList",  "Path_L",     "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Path_R",     "", "", 5)

        obj.addProperty("App::PropertyBool",     "EdgesInverted", "Information", "", 1).EdgesInverted = False

        obj.addProperty("App::PropertyString",    "LeftEdgeName", "", "", 5)
        obj.addProperty("App::PropertyString",    "RightEdgeName", "", "", 5)

        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",    "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",   "Information", "Right Segment length",   1)
        obj.addProperty("App::PropertyLength",      "DiscretizationStep",   "Information", "Discretization step")
        obj.addProperty("App::PropertyInteger",     "PointsCount",          "Information", "Number of points", 1)

        obj.addProperty("App::PropertyDistance",    "LeftEdgeLength",     "", "", 5) 
        obj.addProperty("App::PropertyDistance",    "RightEdgeLength",     "", "", 5)

        obj.addProperty("App::PropertyBool",        "AddPause",             "Task", "Add pause at the end of move").AddPause = False
        obj.addProperty("App::PropertyTime",        "PauseDuration",        "Task", "Pause duration seconds").PauseDuration = job.PauseDuration
        obj.addProperty("App::PropertyBool",        "RapidMove",            "Task", "Move trough this segment with rapid movement speed").RapidMove = False

        obj.addProperty("App::PropertyEnumeration", "CompensationDirection", "Kerf Compensation",   "Kerf compensation direction").CompensationDirection = FC_KERF_DIRECTIONS
        obj.CompensationDirection = 0 # Normal compensation by default

        obj.setExpression(".DiscretizationStep", jobExpression(job, "DiscretizationStep"))

        obj.setEditorMode("PauseDuration", 3)

    def getRoutes(self, obj):
        '''
        Return the routes that use this movement object.
        '''
        return getRoutesForObject(obj)

    def recomputeRoutes(self, obj):
        '''
        Recompute the routes that use this movement object.
        '''
        return recomputeRoutesForObject(obj)

    def onDocumentRestored(self, obj):
        touched = False   
        dir = 0
        # Migrating from 0.1.2 to 0.1.3 - this properties needed for dynamic kerf compensation
        if not hasattr(obj, "LeftEdgeLength"):
            obj.addProperty("App::PropertyDistance",    "LeftEdgeLength",     "", "", 5)   
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - adding LeftEdgeLength property.\n".format(obj.Label))
            touched = True
        if not hasattr(obj, "RightEdgeLength"):
            obj.addProperty("App::PropertyDistance",    "RightEdgeLength",     "", "", 5)
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - adding RightEdgeLength property.\n".format(obj.Label))  
            touched = True
        if hasattr(obj, "KerfCompensationDirection"):
            dir = FC_KERF_DIRECTIONS.index(obj.KerfCompensationDirection) if obj.KerfCompensationDirection in FC_KERF_DIRECTIONS else 0            
            obj.removeProperty("KerfCompensationDirection")
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - removing KerfCompensationDirection property.\n".format(obj.Label))  
            touched = True
        if not hasattr(obj, "CompensationDirection"):
            obj.addProperty("App::PropertyEnumeration", "CompensationDirection", "Kerf Compensation",   "Kerf compensation direction").CompensationDirection = FC_KERF_DIRECTIONS
            obj.CompensationDirection = dir
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDirection property.\n".format(obj.Label))  
            touched = True
        # - Migrating to 0.2.2 - Path and Projection kerf direction is user
        #   selectable now; older documents saved it hidden and read-only.
        if obj.Type in ("Path", "Projection") and hasattr(obj, "CompensationDirection"):
            mode = obj.getEditorMode("CompensationDirection")
            if "Hidden" in mode or "ReadOnly" in mode:
                obj.setEditorMode("CompensationDirection", 0)
                App.Console.PrintMessage("{} - Migrating to 0.2.2 - enabling CompensationDirection for {}.\n".format(obj.Label, obj.Type))
        if not hasattr(obj, "RapidMove"):
            obj.addProperty("App::PropertyBool",        "RapidMove",            "Task", "Move trough this segment with rapid movement speed").RapidMove = False
            App.Console.PrintMessage("{} - Migrating from 0.1.9 to 0.1.10 - adding RapidMove property.\n".format(obj.Label))  
            touched = True
        if touched:
            obj.recompute()

    def onChanged(self, obj, prop):        
        if prop == "AddPause":
            if obj.AddPause:
                obj.setEditorMode("PauseDuration", 0)
            else:
                obj.setEditorMode("PauseDuration", 3)

    def getEdgeEnds(self, edge):
        '''
        Get start and end vertexes of an edge or a single vertex.
        @param edge - edge, wire or vertex
        @returns tuple (start vertex, end vertex)
        '''
        if edge is None:
            return (None, None)

        if isinstance(edge, Part.Vertex):
            return (edge, edge)

        return (edge.firstVertex(), edge.lastVertex())

    def getPairedVertex(self, vertex, leftStart, leftEnd, rightStart, rightEnd, inverted):
        '''
        Get the wire end paired with the given source edge end.
        Path_L[i] and Path_R[i] are the two ends of the same wire, so when the
        right edge is inverted its ends are paired in the opposite order.
        @returns paired vertex or None if vertex is not an edge end
        '''
        if vertex is leftStart:
            return rightStart if not inverted else rightEnd
        if vertex is leftEnd:
            return rightEnd if not inverted else rightStart
        if vertex is rightStart:
            return leftStart if not inverted else leftEnd
        if vertex is rightEnd:
            return leftEnd if not inverted else leftStart

        return None

    def getPointLineDistance(self, point, first, second):
        '''
        Get the distance from a point to the infinite line through two vertexes.
        @param point - point to check
        @param first - first vertex of the line
        @param second - second vertex of the line
        @returns distance to the line
        '''
        direction = second.Point.sub(first.Point)
        if direction.Length <= 1e-9:
            return point.distanceToPoint(first.Point)

        return point.sub(first.Point).cross(direction).Length / direction.Length

    def resolveOppositeVertex(self, point, parent, left, right, inverted):
        '''
        Resolve the source edge end that owns a point projected to a working plane.
        Every path end is the intersection of the working plane with the line
        between two source edge ends, so the end is resolved by the path index.
        Because the path tie can be resolved on either end of an edge, the
        alternate pairing is checked against the same line and used when the
        index pairing does not lie on it.
        @param point - point on a working plane
        @param parent - movement object that owns the point
        @param left - left source edge
        @param right - right source edge
        @param inverted - True if the right edge is inverted
        @returns tuple (isLeft, vertex, oppositeVertex)
        '''
        leftStart, leftEnd = self.getEdgeEnds(left)
        rightStart, rightEnd = self.getEdgeEnds(right)

        isStart = None
        if isCommonPoint(parent.Path_L[START], point) or isCommonPoint(parent.Path_R[START], point):
            isStart = True
        elif isCommonPoint(parent.Path_L[END], point) or isCommonPoint(parent.Path_R[END], point):
            isStart = False

        if isStart is None:
            # - Not a path end: fall back to the nearest source edge end.
            return self.matchNearestVertex(point, left, right, inverted)

        if isStart:
            nominal   = (leftStart, rightEnd if inverted else rightStart)
            alternate = (leftEnd,   rightStart if inverted else rightEnd)
        else:
            nominal   = (leftEnd,   rightStart if inverted else rightEnd)
            alternate = (leftStart, rightEnd if inverted else rightStart)

        pair = nominal
        if self.getPointLineDistance(point, nominal[0], nominal[1]) > WIRE_LINE_TOLERANCE:
            if self.getPointLineDistance(point, alternate[0], alternate[1]) <= WIRE_LINE_TOLERANCE:
                pair = alternate

        # - Working planes are outside the foam, so the nearer end of the wire is
        #   the one that owns the selected point.
        if point.distanceToPoint(pair[0].Point) <= point.distanceToPoint(pair[1].Point):
            (vertex, oppositeVertex) = pair
        else:
            (oppositeVertex, vertex) = pair

        isLeft = vertex is leftStart or vertex is leftEnd
        return (isLeft, vertex, oppositeVertex)

    def matchNearestVertex(self, point, left, right, inverted):
        '''
        Match a point with the nearest source edge end and return its pair.
        @returns tuple (isLeft, vertex, oppositeVertex)
        '''
        leftStart, leftEnd = self.getEdgeEnds(left)
        rightStart, rightEnd = self.getEdgeEnds(right)

        nearestVertex = None
        nearestIsLeft = False
        nearestDistance = None

        for end, isLeft in ((leftStart, True), (leftEnd, True), (rightStart, False), (rightEnd, False)):
            if end is None:
                continue

            distance = point.distanceToPoint(end.Point)
            if nearestDistance is None or distance < nearestDistance:
                nearestVertex = end
                nearestIsLeft = isLeft
                nearestDistance = distance

        oppositeVertex = self.getPairedVertex(
            nearestVertex, leftStart, leftEnd, rightStart, rightEnd, inverted)

        return (nearestIsLeft, nearestVertex, oppositeVertex)

    def matchOppositeVertex(self, vertex, left, right, inverted):
        '''
        Match a selected source vertex with an edge end and return its pair.
        @returns tuple (isLeft, vertex, oppositeVertex) or None if not matched
        '''
        leftStart, leftEnd = self.getEdgeEnds(left)
        rightStart, rightEnd = self.getEdgeEnds(right)

        for end, isLeft in ((leftStart, True), (leftEnd, True), (rightStart, False), (rightEnd, False)):
            if end is not None and isCommonPoint(end, vertex):
                oppositeVertex = self.getPairedVertex(
                    end, leftStart, leftEnd, rightStart, rightEnd, inverted)
                return (isLeft, end, oppositeVertex)

        return None

    def findOppositeVertexes(self, obj, parent, vertex):
        oppositeVertex = None

        doc = obj.Document

        job = doc.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            raise Exception(f"ERROR: Active Job not found\n")

        wp = getWorkingPlanes(job, doc)
        if wp is None:
            return None

        # check if selected vertex laying on any working plane
        onLeftPlane = isclose(wp[0].Position.x, vertex.Point.x, abs_tol=1e-7)
        onRightPlane = isclose(wp[1].Position.x, vertex.Point.x, abs_tol=1e-7)
        onPlane = onLeftPlane or onRightPlane

        isLeft = False

        # get edges or vertices on object we cut from parent action (move, join, path...)
        (left, right) = self.getEdges(parent)
        if left is None or right is None:
            raise Exception(f"ERROR: {parent.Label} has no edges to resolve the opposite vertex.\n")

        if onPlane:
            if isMovement(parent):
                # - Working planes are outside the foam, so the selected point is
                #   a projection of a wire end. Find the source end that owns it
                #   by distance and take the paired end on the other side.
                (isLeft, vertex, oppositeVertex) = self.resolveOppositeVertex(
                    vertex.Point, parent, left, right, bool(parent.EdgesInverted))
            else:
                raise Exception(f"ERROR: Not supported parent object type. Only Path, Move and Projection supported.\n")
        else:
            # - Selected vertex is a source edge end or a model vertex.
            if isMovement(parent):
                result = self.matchOppositeVertex(vertex, left, right, bool(parent.EdgesInverted))
                if result is not None:
                    (isLeft, vertex, oppositeVertex) = result
            else:
                for object in job.Group:
                    if not isMovement(object):
                        continue

                    (objectLeft, objectRight) = self.getEdges(object)
                    if objectLeft is None or objectRight is None:
                        continue

                    result = self.matchOppositeVertex(
                        vertex, objectLeft, objectRight, bool(object.EdgesInverted))
                    if result is not None:
                        (isLeft, vertex, oppositeVertex) = result
                        break

        return (isLeft, vertex, oppositeVertex, wp)

    def getAdditionalShapes(self, obj):
        '''
        Some objects (like Enter) may have additional shapes to display in 3D view (like plunge-down lines). 
        This method should be overridden in such cases to provide those shapes.
        
        :param self: Movement object
        :returns: List of additional shapes to display in 3D view
        '''
        return []

    def createShape(self, obj, edges, planes, color):
        # - Make path between objects on working planes
        discretizationStep = obj.DiscretizationStep if obj.DiscretizationStep > 0 else 0.5
        if len(edges) == 2:
            isLine = isStraitLine(edges[0]) and isStraitLine(edges[1])
            (path_points, inverted, points_count) = makePathPointsByEdgesOrVerticesPair(edges[0], edges[1], planes, discretizationStep, isLine)
        elif len(edges) == 1:
            (path_points, inverted, points_count) = makePathPointsByEdgeOrVertex(edges[0], planes, discretizationStep, isStraitLine(edges[0]))
        else:
            raise Exception(f"ERROR: Not supported number of edges: {len(edges)}.\n")

        if path_points is None:
            raise Exception(f"ERROR: Can't create path for movement - path points are empty.\n")
        
        # - Set data
        obj.Path_L       = [item for item in path_points[START]]
        obj.Path_R       = [item for item in path_points[END]]        
        obj.PointsCount  = points_count
        #

        obj.EdgesInverted = inverted

        shapes = []
        l_points = obj.Path_L
        r_points = obj.Path_R
        
        if obj.PointsCount == 1:
            shapes = [Part.Point(obj.Path_L[START]), Part.Point(obj.Path_R[START])]
            obj.LeftSegmentLength = 0.0
            obj.RightSegmentLength = 0.0   
            obj.LeftEdgeLength = 0.0
            obj.RightEdgeLength = 0.0
        else:
            if len(edges) == 1:
                sameY = True
                tempY = obj.Path_L[START].y
                for point in obj.Path_L:
                    if tempY != point.y:
                        sameY = False
                        break

                if sameY:
                    minZ = min(obj.Path_L, key=lambda point: point.z)
                    maxZ = max(obj.Path_L, key=lambda point: point.z)
                    
                    l_points = [minZ, maxZ]
                    
                    minZ = min(obj.Path_R, key=lambda point: point.z)
                    maxZ = max(obj.Path_R, key=lambda point: point.z)
                    
                    r_points = [minZ, maxZ]

            # - Create path for L
            path_L = Part.BSplineCurve()
            path_L.approximate(Points = l_points, Continuity="C0")

            # - Create path for R
            path_R = Part.BSplineCurve()
            path_R.approximate(Points = r_points, Continuity="C0")
            
            obj.LeftSegmentLength = float(path_L.length())
            obj.RightSegmentLength = float(path_R.length())

            if len(edges) == 1:
                obj.LeftEdgeLength = obj.RightEdgeLength = edges[0].Length
            else:
                obj.LeftEdgeLength = edges[0].Length
                obj.RightEdgeLength = edges[1].Length

            shapes = [path_L.toShape(), path_R.toShape()]

        self.validateWireStretch(obj)
        
        for edge in edges:
            shapes.append(edge)

        # show additional shapes if needeed (like plunge down lines for Enter)
        for shape in self.getAdditionalShapes(obj):
            shapes.append(shape)
        
        obj.Shape = Part.makeCompound(shapes)
        if obj.ViewObject is not None:
            obj.ViewObject.LineColor = color
            obj.ViewObject.PointColor = color

        if hasattr(obj, "LeftEdgeName"):
            obj.LeftEdgeName = "%s%d" % (edges[0].ShapeType, shapes.index(edges[0]) + 1)
        if hasattr(obj, "RightEdgeName") and len(edges) > 1:
            obj.RightEdgeName = "%s%d" % (edges[1].ShapeType, shapes.index(edges[1]) + 1)

    def validateWireStretch(self, obj):
        job = getJob(obj)

        if not job.WireStretchVerification or not float(job.WireStretchLength) > 0.0:
            return True

        if len(obj.Path_L) != len(obj.Path_R):
            raise Exception(f"ERROR: Number of points doesn't match. Object - {obj.Label}")
        
        delta = float(job.WireStretchLength)
        wireLength = float(job.FieldWidth)

        for pL, pR in zip(obj.Path_L, obj.Path_R):
            stretch = pL.distanceToPoint(pR) - wireLength

            if stretch > delta:
                App.Console.PrintWarning(f"Warning:\n Wire about to break cutting {obj.Label}. Wire stretch is {stretch:.2f}mm that is greater than allowed {delta:.2f}mm \n")
                return False

        return True
