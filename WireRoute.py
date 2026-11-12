__title__ = "Create Route"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create a route from selected paths."
__usage__ = """Select multiple paths in order of cutting and activate tool."""

import FreeCAD
App=FreeCAD
import Part
import FoamCutBase
from utilities import *

FC_KERF_STRATEGY_NONE = 0
FC_KERF_STRATEGY_UNI = 1
FC_KERF_STRATEGY_DYN = 2

SUPPRESS_WARNINGS = getParameterBool("SuppressWarnings", True)

class FoamCut_RouteSegment():
    def __init__(self):
        self.Edges = []
        self.LastPoint = 0
        self.LeftPlaneX = 0.0
        self.RightPlaneX = 0.0
        self.PathLeft = []
        self.PathRight = []
        self.SimpleProjection = False

class FoamCut_RouteEdge():
    def __init__(self):
        self.PointsCount = 0
        self.PointsLeft = []
        self.PointsRight = []
        self.OffsetLeft = []
        self.OffsetRight = []
        self.OffsetLenLeft = 0
        self.OffsetLenRight = 0
        self.CompensationDirection = 0
        self.LeftEdgeLength = None
        self.RightEdgeLength = None
        self.LeftSegmentLength = None
        self.RightSegmentLength = None
        self.PauseDuration = None

        self.DataIdx = 0
        self.ObjectType = None

    def projectToPlanes(self, leftPlane, rightPlane):
        if self.PointsCount <= 1 or self.LeftEdgeLength <= 1e-2 or self.RightEdgeLength <= 1e-2:
            # edge is too short or a single point - no need to make offset
            return
        
        projectedLeft = []
        projectedRight = []

        for i in range(len(self.PointsLeft)):
            projectedLeft.append(intersectLineAndPlane(self.PointsLeft[i], self.PointsRight[i], leftPlane))
            projectedRight.append(intersectLineAndPlane(self.PointsLeft[i], self.PointsRight[i], rightPlane))

        self.PointsLeft = projectedLeft
        self.PointsRight = projectedRight

        # recalculate edges length
        path_L = Part.BSplineCurve()
        path_L.approximate(Points = projectedLeft, Continuity="C0")

        path_R = Part.BSplineCurve()
        path_R.approximate(Points = projectedRight, Continuity="C0")
        
        self.LeftEdgeLength = float(path_L.length())
        self.RightEdgeLength = float(path_R.length())

    def makeOffset(self, dynamic = False, degree=1.0):
        if self.PointsCount <= 1 or self.LeftEdgeLength <= 1e-2 or self.RightEdgeLength <= 1e-2:
            # edge is too short or a single point - no need to make offset
            return
        
        if dynamic:
            #calculate compensation for the sides
            ratio = max(self.LeftEdgeLength, self.RightEdgeLength) / min(self.LeftEdgeLength, self.RightEdgeLength)

            # if edge is slower than nominal speed - increase compensation.
            # degree is a dampening factor
            compensation = ratio ** degree if degree > 1 else ratio

            if self.LeftEdgeLength > self.RightEdgeLength:
                self.OffsetLenRight *= compensation
            else:
                self.OffsetLenLeft *= compensation

        lWire = makeWireOffset(makeWire(self.PointsLeft), self.OffsetLenLeft)
        rWire = makeWireOffset(makeWire(self.PointsRight), self.OffsetLenRight)        
        self.OffsetLeft = [v.Point for v in lWire.Vertexes]
        self.OffsetRight = [v.Point for v in rWire.Vertexes]

    def getFeedOverride(self):
        maxEdgeLength = max(self.LeftEdgeLength, self.RightEdgeLength)
        maxSegmentLength = max(self.LeftSegmentLength, self.RightSegmentLength)
        if maxEdgeLength == 0:
            return 1.0
        
        return maxSegmentLength/maxEdgeLength


def validateRoute(objects):
    '''
    Validates the route structure before the pair loop runs:
    - the route must not start with an Exit (plunge-up before any cut)
    - the route must not end with an Enter (plunge-down without a cut)
    - Rotation objects may only appear at segment boundaries:
      preceded by an Exit or by nothing (route start),
      followed by an Enter or by nothing (route end)
    Single-point Projections (PointsCount < 2) are always skipped - they
    produce no cut and are transparent to these checks.
    Raises an Exception (aborting route creation) on any violation.
    '''
    prev = None
    first = None
    last = None

    for obj in objects:
        if obj.Type == "Projection" and obj.PointsCount < 2:
            continue

        if first is None:
            first = obj
        last = obj

        if obj.Type == "Rotation":
            if prev is not None and prev.Type != "Exit":
                raise Exception(f"ERROR: {obj.Label} - Rotation must be preceded by an Exit (or be the first command). Mid-route rotations are not allowed.")
            prev = obj
            continue

        if prev is not None and prev.Type == "Rotation" and obj.Type != "Enter":
            raise Exception(f"ERROR: {prev.Label} - Rotation must be followed by an Enter (or be the last command). Mid-route rotations are not allowed.")

        prev = obj

    if first is not None and first.Type == "Exit":
        raise Exception(f"ERROR: {first.Label} - Unsupported first element. Route cannot start with Exit.")
    if last is not None and last.Type == "Enter":
        raise Exception(f"ERROR: {last.Label} - Unsupported last element. Route cannot end with Enter.")


def getRoutePointLayout(route):
    '''
    Map the flattened route points to the objects that produced them.
    The route builder appends every object's points except its last one (the
    shared point is contributed by the next object), prepends an Enter plunge
    and appends an Exit last point plus plunge. This function reproduces that
    accounting from Data/Objects without touching the stored points.
    @param route - Route object
    @returns list of tuples (object, start_index, point_count)
    '''
    data = list(getattr(route, "Data", []))
    objects = list(getattr(route, "Objects", []))

    last_movement = -1
    for position, object_index in enumerate(data):
        if objects[object_index].Type != "Rotation":
            last_movement = position

    blocks = []
    index = 0
    for position, object_index in enumerate(data):
        object = objects[object_index]
        if object.Type == "Rotation":
            continue

        points_count = int(object.PointsCount)
        if object.Type == "Enter":
            path_count = points_count + (1 if getattr(object, "LeadInEnabled", False) else 0)
            count = 1 + max(path_count - 2, 0)
        elif object.Type == "Exit":
            count = points_count + 1
        else:
            count = points_count if position == last_movement else points_count - 1

        blocks.append((object, index, count))
        index += count

    total = len(getattr(route, "Offset_L", []))
    if index != total:
        raise Exception("ERROR: Route [{}] point layout does not match its points: {} mapped, {} stored. Recompute the route.".format(route.Label, index, total))
    return blocks

def mirrorRoutePointsXY(route, points, pivot):
    '''
    Reflect one side of a route about a horizontal plane.
    Plunge points stay at safe height, Enter/Exit anchor points are mirrored
    and their leads are rebuilt from the mirrored anchor with the original
    offset vector; every other point is simply reflected.
    @param route - Route object (for the object layout)
    @param points - one side's flattened points
    @param pivot - vertical pivot
    @returns new list of points
    '''
    blocks = getRoutePointLayout(route)
    result = list(points)

    for block_index, (object, start, count) in enumerate(blocks):
        if count <= 0:
            continue
        end = start + count

        if object.Type == "Enter":
            if block_index + 1 >= len(blocks):
                raise Exception("ERROR: Enter [{}] has no following route point; cannot rebuild its lead.".format(object.Label))
            entry = points[blocks[block_index + 1][1]]
            mirrored_entry = App.Vector(entry.x, entry.y, 2.0 * float(pivot) - entry.z)
            for i in range(start + 1, end):
                result[i] = mirrored_entry + (points[i] - entry)

        elif object.Type == "Exit":
            exit_point = points[start]
            mirrored_exit = App.Vector(exit_point.x, exit_point.y, 2.0 * float(pivot) - exit_point.z)
            result[start] = mirrored_exit
            for i in range(start + 1, end - 1):
                result[i] = mirrored_exit + (points[i] - exit_point)

        else:
            for i in range(start, end):
                result[i] = App.Vector(points[i].x, points[i].y, 2.0 * float(pivot) - points[i].z)

    return result

class WireRoute(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, objects, jobName):   
        super().__init__(obj, jobName)     
        obj.Type = "Route"          
        obj.addProperty("App::PropertyVectorList",  "Offset_L",         "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Offset_R",         "", "", 5)

        obj.addProperty("App::PropertyIntegerList", "RouteBreaks",      "", "", 5) # indexes of a points where route breaks - Rotation

        obj.addProperty("App::PropertyIntegerList", "Pauses",           "", "", 5) # indexes of a points where should be pause
        obj.addProperty("App::PropertyFloatList",   "PausesDurations",  "", "", 5) 

        obj.addProperty("App::PropertyFloatList",   "FeedOverrides",  "", "", 5) 

        obj.addProperty("App::PropertyInteger",     "Redraw",           "", "", 5).Redraw = 0 # property to tgger view provider to update 

        obj.addProperty("App::PropertyLinkList",    "Objects",          "Task",   "Source data").Objects = objects
        obj.addProperty("App::PropertyIntegerList", "Data",             "Task",   "Data")
        obj.addProperty("App::PropertyBoolList",    "DataDirection",    "Task",   "Data Direction")

        obj.addProperty("App::PropertyLength",      "KerfCompensation",         "Kerf Compensation",   "Kerf Compensation")
        obj.addProperty("App::PropertyEnumeration", "CompensationDirection",    "Kerf Compensation",   "Kerf compensation direction.").CompensationDirection = FC_ROUTE_KERF_DIRECTIONS 
        obj.CompensationDirection = 0

        obj.addProperty("App::PropertyEnumeration", "CompensationStrategy",     "Kerf Compensation",   "Kerf compensation strategy. \r\n\
                            None - do no compensate for kerf. \r\n\
                            Uniform - same amount of compensation on both sides. Doesn'd take into account wire speed. \r\n\
                            Dynamic - compensation depends on wire speed (that depends on edge length). Slower speed - more compensation.").CompensationStrategy = FC_KERF_STRATEGY 
        obj.CompensationStrategy = 0   

        obj.addProperty("App::PropertyFloat",     "CompensationDegree",        "Kerf Compensation",    "Kerf Compensation coefficient. \r\n\
                        This coefficient help calculate kerf compensation when wire speed is less than nominal. \r\n\
                        Usually kerf thickness is directly related to movement speed. Lesser speed - thicker kerf. \
                        But in some foams it will not be that simple, since wire melts foam and it became dencer. \r\n\
                        Normally it should be 1.0, but for denser foam it could be bigger.")
        obj.setEditorMode("CompensationDegree", 2)
        config = self.getConfigName(obj)

        obj.setExpression(".KerfCompensation", u"<<{}>>.KerfCompensation".format(config))
        obj.setExpression(".CompensationDegree", u"<<{}>>.CompensationDegree".format(config))
        
        obj.Proxy = self
        #self.execute(obj)

    def getSourceRoute(self, obj):
        '''
        Return the route that owns the geometry.
        A plain route owns it; a clone overrides this with its Source link.
        '''
        return obj

    def getOutputPoints(self, obj):
        '''
        Return the route points used by the viewport and the postprocessor.
        '''
        return (list(obj.Offset_L), list(obj.Offset_R))

    def getRotationAngle(self, obj, angle):
        '''
        Return the rotation angle to emit. A mirrored clone overrides this.
        '''
        return float(angle)
    
    def onDocumentRestored(self, obj):
        touched = False
        if hasattr(obj, "DynamicKerfCompensation"):
            dynamic = obj.DynamicKerfCompensation       
            obj.removeProperty("DynamicKerfCompensation")
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - removing DynamicKerfCompensation property.\n".format(obj.Label))  
            touched = True

        # Migrating from 0.1.2 to 0.1.3 - this properties needed for dynamic kerf compensation
        if not hasattr(obj, "CompensationStrategy"):
            obj.addProperty("App::PropertyEnumeration", "CompensationStrategy",    "Kerf Compensation",   "Kerf compensation strategy. \r\n\
                            None - do no compensate for kerf. \r\n\
                            Uniform - same amount of compensation on both sides. Doesn'd take into account wire speed. \r\n\
                            Dynamic - compensation depends on wire speed (that depends on edge length). Slower speed - more compensation.").CompensationStrategy = FC_KERF_STRATEGY 
            obj.CompensationStrategy = FC_KERF_STRATEGY.index("Dynamic") if dynamic else 0
                               
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationStrategy property.\n".format(obj.Label))
            touched = True

        if not hasattr(obj, "CompensationDegree"):
            obj.addProperty("App::PropertyFloat",     "CompensationDegree",      "Kerf Compensation",    "Kerf Compensation coefficient. \r\n\
                        This coefficient help calculate kerf compensation when wire speed is less than nominal. \r\n\
                        Usually kerf thickness is directly related to movement speed. Lesser speed - thicker kerf. \
                        But in some foams it will not be that simple, since wire melts foam and it became dencer. \r\n\
                        Normally it should be 1.0, but for denser foam it could be bigger.")
            obj.setEditorMode("CompensationDegree", 2)
            config = self.getConfigName(obj)            
            obj.setExpression(".CompensationDegree", u"<<{}>>.CompensationDegree".format(config))
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDegree property.\n".format(obj.Label))
            touched = True

        if hasattr(obj, "KerfCompensation") and obj.getGroupOfProperty("KerfCompensation") != "Kerf Compensation":
            obj.setGroupOfProperty("KerfCompensation", "Kerf Compensation")
        
        if hasattr(obj, "FlipKerfCompensation"):
            dir = 1 if obj.FlipKerfCompensation else 0            
            obj.removeProperty("FlipKerfCompensation")
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - removing FlipKerfCompensation property.\n".format(obj.Label))  
            touched = True

        if not hasattr(obj, "CompensationDirection"):
            obj.addProperty("App::PropertyEnumeration", "CompensationDirection",   "Kerf Compensation",   "Kerf compensation direction.").CompensationDirection = FC_ROUTE_KERF_DIRECTIONS 
            obj.CompensationDirection = dir
            App.Console.PrintMessage("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDirection property.\n".format(obj.Label))
            touched = True

        if not hasattr(obj, "FeedOverrides"):
            obj.addProperty("App::PropertyFloatList",   "FeedOverrides",  "", "", 5) 
            App.Console.PrintMessage("{} - Migrating from 0.1.10 to 0.1.11 - adding FeedOverrides property.\n".format(obj.Label))
            touched = True
            
        if touched:
            obj.recompute()

    def execute(self, obj):
        # start_time = time.perf_counter()

        config = self.getConfig(obj)

        doc = obj.Document

        job = doc.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            raise Exception("ERROR: Error updating Enter - active Job not found\n")

        (wpl, wpr) = getWorkingPlanes(job, doc)

        validateRoute(obj.Objects)

        first       = obj.Objects[0]
        reversed    = None        # - Second segment is reversed
        route_data  = []
        route_data_dir  = []
        item_index  = 0
        pauses = []
        pausesDuration = []
        breaks = []

        # lastObjectPoint tracks global index in flattened Path_L / Path_R
        lastObjectPoint = 0

        # - Check is single element
        if len(obj.Objects) == 1:
            # - Store element            
            route_data.append(item_index)
            route_data_dir.append(False)
            object = obj.Objects[item_index]

            # skip rotation object
            if hasattr(object, "PointsCount"):
                lastObjectPoint = object.PointsCount - 1

        # - Walk through other objects
        for second in obj.Objects[1:]:
            item_index += 1

            # - Process skipped element
            if first is None:
                first = second
                if first.Type == "Enter" and reversed is not None:
                    route_data.append(item_index)
                    route_data_dir.append(False)
                    lastObjectPoint += first.PointsCount - 1

                #print("SKIP: %s" % second.Type)               
                continue
            
            if first.Type == "Projection" and first.PointsCount < 2:
                # print("Vertex Projection - skip")
                first = second
                continue

            # - Skip rotation object
            if first.Type == "Rotation":
                #print("R1")
                # - Store first element
                route_data.append(item_index - 1)
                route_data_dir.append(False)
                breaks.append(lastObjectPoint)

                # - Check is rotation is first element
                if item_index == 1:
                    # - Do not skip next element
                    first = second
                    continue
                else:
                    # - Go to next object
                    first = None
                    continue
            elif second.Type == "Rotation":
                #print("R1 - 2")
                # - Store element
                route_data.append(item_index)
                route_data_dir.append(False)
                breaks.append(lastObjectPoint)

                # - Skip element
                first = None
                reversed = None
                continue
            elif first.Type == "Exit" and second.Type == "Enter":
                #print("EXIT -> ENTER")
                #print("reversed: {}".format(reversed))
                # - Store first item
                if len(route_data) == 0:
                    # - Store element
                    route_data.append(item_index - 1)
                    route_data_dir.append(False)

                    lastObjectPoint += first.PointsCount - 1


                # - Store element
                route_data.append(item_index)
                route_data_dir.append(False)

                breaks.append(lastObjectPoint)

                lastObjectPoint += second.PointsCount - 1

                first = second
                reversed = False # enter always normal
                continue
            
            # - Get lines on left plane
            if isMovement(first) or first.Type == "Enter":
                first_line  = first.Path_L
            else:
                raise Exception(f"ERROR: {first.Label} - Unsupported first element. Second = {second.Label}")
            
            if isMovement(second) or second.Type == "Exit": 
                second_line = second.Path_L
            else:
                raise Exception(f"ERROR: {second.Label} - Unsupported second element. First = {first.Label}")
            
            if reversed is None:
                first_reversed = False
                
                # - Detect first pair
                if isCommonPoint(first_line[END], second_line[START]):
                    #print ("First connected: FWD - FWD")
                    reversed = False
                elif isCommonPoint(first_line[END], second_line[END]):
                    #print ("First connected: FWD - REV")
                    reversed = True
                elif isCommonPoint(first_line[START], second_line[START]):
                    #print ("First connected: REV - FWD")
                    first_reversed  = True
                    reversed        = False
                elif isCommonPoint(first_line[START], second_line[END]):
                    #print ("First connected: REV - REV")
                    first_reversed  = True
                    reversed        = True
                else:
                    raise Exception(f"ERROR: {first.Label} not connected with {second.Label}")
                
                # - Store first element
                route_data.append(item_index - 1)
                route_data_dir.append(first_reversed)

                lastObjectPoint += first.PointsCount - 1


            else:                
                # - Detect next pairs
                if isCommonPoint(first_line[START if reversed else END], second_line[START]):
                    #print ("Connected: FWD - FWD")
                    reversed = False
                elif isCommonPoint(first_line[START if reversed else END], second_line[END]):
                    #print ("Connected: FWD - REV")
                    reversed = True
                else:
                    raise Exception(f"ERROR: {first.Label} not connected with {second.Label}")

            # - Store second element
            route_data.append(item_index)
            route_data_dir.append(reversed)

            lastObjectPoint += second.PointsCount - 1

            # - Go to next object
            first = second
        
        if len(route_data) != len(route_data_dir) or len(route_data) == 0:
            raise Exception("Error: Data calculation error.")
        
        obj.Data = route_data
        obj.DataDirection = route_data_dir

        # - try to make a offset       
        resultPoints_L = []
        resultPoints_R = []

        # list of route segments
        segments = []
        currentSegment = FoamCut_RouteSegment()
        currentEdge = FoamCut_RouteEdge()

        for i in range(len(route_data)): 
            # - dead code: "Rotation" is never set (rotation edges hit `continue`
            #   before ObjectType is assigned), so the split is driven by "Exit" only.
            if currentEdge.ObjectType == "Rotation" or currentEdge.ObjectType == "Exit":
                segments.append(currentSegment)
                currentSegment = FoamCut_RouteSegment()                    

            currentEdge = FoamCut_RouteEdge()
            
            # - Access item
            object = obj.Objects[route_data[i]]
                
            # Always skip rotation
            if object.Type == "Rotation":                                   
                continue

            pointsCount = object.PointsCount

            if object.Type == "Enter" and object.LeadInEnabled:
                pointsCount += 1

            currentEdge.DataIdx = i
            currentEdge.ObjectType = object.Type
            currentEdge.PointsCount = pointsCount
            currentEdge.CompensationDirection = object.CompensationDirection

            currentEdge.LeftEdgeLength = float(object.LeftEdgeLength) if object.LeftEdgeLength > 0 else 0.1
            currentEdge.RightEdgeLength = float(object.RightEdgeLength) if object.RightEdgeLength > 0 else 0.1

            currentEdge.LeftSegmentLength = float(object.LeftSegmentLength) if object.LeftSegmentLength > 0 else 0.1
            currentEdge.RightSegmentLength = float(object.RightSegmentLength) if object.RightSegmentLength > 0 else 0.1

            currentEdge.PointsLeft = currentEdge.OffsetLeft = object.Path_L[::-1] if route_data_dir[i] else object.Path_L
            currentEdge.PointsRight = currentEdge.OffsetRight = object.Path_R[::-1] if route_data_dir[i] else object.Path_R

            currentSegment.LastPoint += pointsCount - 1

            if hasattr(object, "AddPause") and object.AddPause:
                pauses.append(currentSegment.LastPoint)
                pausesDuration.append(float(object.PauseDuration)) 

            if not currentSegment.SimpleProjection:
                if object.Type == "Projection":
                    currentSegment.SimpleProjection = True
                else:
                    (left, right) = self.getEdges(object)
                    if left is not None and right is not None:
                        currentSegment.LeftPlaneX = left.BoundBox.XMin if left.BoundBox.XMin < currentSegment.LeftPlaneX else currentSegment.LeftPlaneX
                        currentSegment.RightPlaneX = right.BoundBox.XMax if right.BoundBox.XMax > currentSegment.RightPlaneX else currentSegment.RightPlaneX
                    else:
                        currentSegment.SimpleProjection = True

            currentSegment.Edges.append(currentEdge)

        # - dead code: "Rotation" is never set (same reason as the segment-split check above).
        #   trailing Rotation is always preceded by an Exit
        if currentEdge.ObjectType != "Rotation":
            segments.append(currentSegment)

        applyKerf = obj.KerfCompensation > 0 and FC_KERF_STRATEGY.index(obj.CompensationStrategy) > FC_KERF_STRATEGY_NONE

        # apply kerf compensation if needed
        if applyKerf:
            # build temporary planes for projection
            # and make offsets from resulted projections
            for i, segment in enumerate(segments):                
                norm = App.Vector(1.0, 0.0, 0.0)
                xdir = App.Vector(0.0, 1.0, 0.0)
                leftPlane = Part.makePlane(float(config.HorizontalTravel), float(config.VerticalTravel), App.Vector(segment.LeftPlaneX, float(-config.OriginX), 0), norm, xdir)
                rightPlane = Part.makePlane(float(config.HorizontalTravel), float(config.VerticalTravel), App.Vector(segment.RightPlaneX, float(-config.OriginX), 0), norm, xdir)

                for j, edge in enumerate(segment.Edges):
                    idx = FC_KERF_DIRECTIONS.index(edge.CompensationDirection) if edge.CompensationDirection in FC_KERF_DIRECTIONS else 0                    
                    dir = -1 * (idx - 1) if obj.CompensationDirection in FC_ROUTE_KERF_DIRECTIONS and FC_ROUTE_KERF_DIRECTIONS.index(obj.CompensationDirection) == 1 else idx - 1
                
                    edge.OffsetLenLeft = float(obj.KerfCompensation) * dir
                    edge.OffsetLenRight = float(obj.KerfCompensation) * dir

                    dynamicOffset = False
                    if not segment.SimpleProjection:
                        #project edges from working planes to temp planes
                        edge.projectToPlanes(leftPlane, rightPlane)

                        dynamicOffset = dir != 0 and FC_KERF_STRATEGY.index(obj.CompensationStrategy) == FC_KERF_STRATEGY_DYN                       

                    # compute offsets
                    edge.makeOffset(dynamicOffset, obj.CompensationDegree)

            # intersect offsets and build final route points
            for i, segment in enumerate(segments):
                firstWire_L = secondWire_L = None
                firstWire_R = secondWire_R = None
                
                last_point_L = None
                last_point_R = None

                for j in range(len(segment.Edges) - 1):
                    edge = segment.Edges[j]
                    if firstWire_L == None and firstWire_R == None:
                        firstWire_L = makeWire(edge.OffsetLeft)
                        firstWire_R = makeWire(edge.OffsetRight)
                    
                    if secondWire_L == None and secondWire_R == None:
                        secondWire_L = makeWire(segment.Edges[j + 1].OffsetLeft)
                        secondWire_R = makeWire(segment.Edges[j + 1].OffsetRight)

                    try:
                        ileft = intersectWires(firstWire_L, secondWire_L, tolerance=5e-3)
                    except Exception as e:
                        raise Exception(f"ERROR: {e}")
                    
                    try:
                        iright = intersectWires(firstWire_R, secondWire_R, tolerance=5e-3)
                    except Exception as e:
                        raise Exception(f"ERROR: {e}")
                    
                    try:
                        off = connectWires(firstWire_L, secondWire_L, ileft)
                    except Exception as e:
                        raise Exception(f"ERROR: LEFT OFFSET Something wrong near point: {ileft}; idx: {j}. Exception: {e}")
                        
                    if off == None:
                        raise Exception(f"ERROR: LEFT OFFSET Something wrong near point: {ileft}; idx: {j}")
                    
                    # - discretize wire so it will have same count of vertices as source wire
                    edge.OffsetLeft = self.getWirepoints(off[0], edge.PointsCount) if edge.PointsCount > 1 else [ileft[0]]

                    firstWire_L = off[1]
                    secondWire_L = None

                    # save last offset point
                    last_point_L = edge.OffsetLeft[-1]

                    try:
                        off = connectWires(firstWire_R, secondWire_R, iright)
                    except Exception as e:
                        raise Exception(f"ERROR: RIGHT OFFSET Something wrong near point: {iright}; idx: {j}. Exception: {e}")
                    
                    if off == None:
                        raise Exception(f"ERROR: RIGHT OFFSET Something wrong near point: {iright}; idx: {j}")
                    
                    # - discretize wire so it will have same count of vertices as source wire
                    edge.OffsetRight = self.getWirepoints(off[0], edge.PointsCount) if edge.PointsCount > 1 else [iright[0]]

                    firstWire_R = off[1]
                    secondWire_R = None

                    # save last offset point
                    last_point_R = edge.OffsetRight[-1]

                    if not segment.SimpleProjection:
                        left_Off = []
                        right_off = []
                        for p in range(edge.PointsCount):
                            left_Off.append(intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpl))
                            right_off.append(intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpr))
                        edge.OffsetLeft = left_Off
                        edge.OffsetRight = right_off

                # add last edge points
                edge = segment.Edges[-1]
                if firstWire_L is not None and firstWire_R is not None:                  
                    edge.OffsetLeft = self.getWirepoints(firstWire_L, edge.PointsCount)
                    edge.OffsetRight = self.getWirepoints(firstWire_R, edge.PointsCount)
                elif edge.PointsCount == 1 and last_point_L is not None and last_point_R is not None:
                    edge.OffsetLeft = [last_point_L]
                    edge.OffsetRight = [last_point_R]

                if not segment.SimpleProjection:
                    left_Off = []
                    right_off = []
                    for p in range(edge.PointsCount):                            
                        left_Off.append(intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpl))
                        right_off.append(intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpr))
                    edge.OffsetLeft = left_Off
                    edge.OffsetRight = right_off

        # build route from segments and edges
        for i, segment in enumerate(segments):
            if len(segment.Edges) > 0:
                for j, edge in enumerate(segment.Edges):
                    pointsCount = edge.PointsCount
                    # check for enter/exit case and add plunge-down or plunge-up lines
                    if edge.ObjectType == "Enter":
                        object = obj.Objects[route_data[edge.DataIdx]]
                        # add plunge down line
                        plunge_L = App.Vector(edge.OffsetLeft[0].x, edge.OffsetLeft[0].y, float(object.SafeHeight))
                        plunge_R = App.Vector(edge.OffsetRight[0].x, edge.OffsetRight[0].y, float(object.SafeHeight))

                        resultPoints_L.append(plunge_L)
                        resultPoints_R.append(plunge_R)

                        # plunge-down start point not included in offset points, but reflected in points count
                        pointsCount -= 1

                    for idx in range(pointsCount - 1):
                        resultPoints_L.append(edge.OffsetLeft[idx])
                        resultPoints_R.append(edge.OffsetRight[idx])
                    
                    if edge.ObjectType == "Exit":
                        object = obj.Objects[route_data[edge.DataIdx]]
                        # add last point of the edge as plunge down line start point.
                        resultPoints_L.append(edge.OffsetLeft[-1])
                        resultPoints_R.append(edge.OffsetRight[-1])

                        # add plunge up line
                        plunge_L = App.Vector(edge.OffsetLeft[-1].x, edge.OffsetLeft[-1].y, float(object.SafeHeight))
                        plunge_R = App.Vector(edge.OffsetRight[-1].x, edge.OffsetRight[-1].y, float(object.SafeHeight))

                        resultPoints_L.append(plunge_L)
                        resultPoints_R.append(plunge_R)

                    # add last point of the last edge. except for exit - it's last point already added as plunge-up line
                    if j == len(segment.Edges) - 1 and edge.ObjectType != "Exit":
                        resultPoints_L.append(edge.OffsetLeft[-1])
                        resultPoints_R.append(edge.OffsetRight[-1])

        # - Build feed overrides aligned with route data entries.
        # - Rotation objects do not produce edges (they have no feed override),
        #   so their entries default to 1.0.
        edgeOverrides = {}
        for segment in segments:
            for edge in segment.Edges:
                edgeOverrides[edge.DataIdx] = edge.getFeedOverride()

        feed_overrides = [edgeOverrides.get(i, 1.0) for i in range(len(route_data))]

        validateWorkingArea(resultPoints_L, resultPoints_R, wpl, wpr)

        obj.Offset_L = resultPoints_L
        obj.Offset_R = resultPoints_R
        obj.Pauses = pauses
        obj.PausesDurations = pausesDuration
        obj.RouteBreaks = breaks
        obj.FeedOverrides = feed_overrides

        obj.Redraw += 1 #change of this property will trigger VP to redraw

    def getEdges(self, obj):
        '''
        Get left and right edges for object
        @param obj - object to get edges for
        @return tuple of (left edge, right edge)
        '''
        if hasattr(obj, "LeftEdgeName") and hasattr(obj, "RightEdgeName") \
            and obj.LeftEdgeName != "" and obj.RightEdgeName != "":

            left = obj.getSubObject(obj.LeftEdgeName)
            right = obj.getSubObject(obj.RightEdgeName)
            return (left, right)
        else:
            return (None, None)
        
    def getWirepoints(self, wire, num_points):
        '''
        Make a Bspline from wire, discretize it with specified number of points
        @param wire - wire to discretize
        @param num_points - number of points
        @return list of points 
        '''
        if num_points == 2: # short strait line - no need to convert
            return [wire.Vertexes[0].Point, wire.Vertexes[-1].Point]
        
        bs = Part.BSplineCurve()
        bs.interpolate([v.Point for v in wire.Vertexes])
        res = bs.discretize(Number=num_points)
        
        return res
    
    def detect_connection(first_line, second_line, first_reversed):
        f_end = first_line[START if first_reversed else END]

        if isCommonPoint(f_end, second_line[START]):
            return False
        if isCommonPoint(f_end, second_line[END]):
            return True

        return None


def createRoute(job, objects, label = None, recompute = True):
    '''
    Create a Route object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param objects - ordered list of movement objects
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Route object
    '''
    doc = job.Document
    route = job.newObject("App::FeaturePython", "Route")
    removed = []
    try:
        WireRoute(route, objects, job.Name)
        if label:
            route.Label = label
        for obj in objects:
            if obj in job.Group:
                job.removeObject(obj)
                removed.append(obj)
    except Exception:
        for obj in removed:
            job.addObject(obj)
        doc.removeObject(route.Name)
        raise

    if recompute:
        doc.recompute()
    return route


def __getattr__(name):
    # - Old documents stored the view provider as WireRoute.WireRouteVP.
    if name == "WireRouteVP":
        from RouteGui import WireRouteVP
        return WireRouteVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
