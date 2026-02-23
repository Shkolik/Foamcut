__title__ = "Create Route"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create a route from selected paths."
__usage__ = """Select multiple paths in order of cutting and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutBase
import FoamCutViewProviders
from utilities import *
import pivy.coin as coin
import math
import time

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

            # # debug - edges lenth ratio
            # print(f"Offset_{self.ObjectType} edge length ratio: {ratio}")

            # if edge is slower than nominal speed - increase compensation.
            # degree is a dampening factor
            compensation = ratio ** degree if degree > 1 else ratio

            if self.LeftEdgeLength > self.RightEdgeLength:
                self.OffsetLenRight *= compensation
            else:
                self.OffsetLenLeft *= compensation
                
        # debug - show original wires
        # print(f"Offset_L_{self.ObjectType} compensated offset: {self.OffsetLenLeft}")
        # print(f"Offset_R_{self.ObjectType} compensated offset: {self.OffsetLenRight}")

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
        self.execute(obj)
    
    def onDocumentRestored(self, obj):
        touched = False
        if hasattr(obj, "DynamicKerfCompensation"):
            dynamic = obj.DynamicKerfCompensation       
            obj.removeProperty("DynamicKerfCompensation")
            print("{} - Migrating from 0.1.2 to 0.1.3 - removing DynamicKerfCompensation property.".format(obj.Label))  
            touched = True

        # Migrating from 0.1.2 to 0.1.3 - this properties needed for dynamic kerf compensation
        if not hasattr(obj, "CompensationStrategy"):
            obj.addProperty("App::PropertyEnumeration", "CompensationStrategy",    "Kerf Compensation",   "Kerf compensation strategy. \r\n\
                            None - do no compensate for kerf. \r\n\
                            Uniform - same amount of compensation on both sides. Doesn'd take into account wire speed. \r\n\
                            Dynamic - compensation depends on wire speed (that depends on edge length). Slower speed - more compensation.").CompensationStrategy = FC_KERF_STRATEGY 
            obj.CompensationStrategy = FC_KERF_STRATEGY.index("Dynamic") if dynamic else 0
                               
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationStrategy property.".format(obj.Label))
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
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDegree property.".format(obj.Label))
            touched = True

        if hasattr(obj, "KerfCompensation") and obj.getGroupOfProperty("KerfCompensation") != "Kerf Compensation":
            obj.setGroupOfProperty("KerfCompensation", "Kerf Compensation")
        
        if hasattr(obj, "FlipKerfCompensation"):
            dir = 1 if obj.FlipKerfCompensation else 0            
            obj.removeProperty("FlipKerfCompensation")
            print("{} - Migrating from 0.1.2 to 0.1.3 - removing FlipKerfCompensation property.".format(obj.Label))  
            touched = True

        if not hasattr(obj, "CompensationDirection"):
            obj.addProperty("App::PropertyEnumeration", "CompensationDirection",   "Kerf Compensation",   "Kerf compensation direction.").CompensationDirection = FC_ROUTE_KERF_DIRECTIONS 
            obj.CompensationDirection = dir
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDirection property.".format(obj.Label))
            touched = True

        if not hasattr(obj, "FeedOverrides"):
            obj.addProperty("App::PropertyFloatList",   "FeedOverrides",  "", "", 5) 
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding FeedOverrides property.".format(obj.Label))
            touched = True
            
        if touched:
            obj.recompute()

    def execute(self, obj):
        # start_time = time.perf_counter()

        try:
            config = self.getConfig(obj)

            doc = obj.Document

            job = doc.getObject(obj.JobName)
            if job is None or job.Type != "Job":
                raise Exception("ERROR: Error updating Enter - active Job not found\n")

            (wpl, wpr) = getWorkingPlanes(job, doc)

            first       = obj.Objects[0]
            reversed    = None        # - Second segment is reversed
            route_data  = []
            route_data_dir  = []
            feed_overrides = []
            item_index  = 0
            feed_overrides  = []
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

                if object.Type == "Exit" and object.LeadOutEnabled:
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
                            # p = Part.show(Part.Vertex(ileft[0]), "Trim point")
                            # p.ViewObject.PointSize = 6
                            # Part.show(firstWire_L, "first wire")
                            # Part.show(secondWire_L, "second wire")
                            # print(f"Failed to trim wire. Info: {ileft}")
                            raise Exception(f"ERROR: {e}")
                        
                        try:
                            iright = intersectWires(firstWire_R, secondWire_R, tolerance=5e-3)
                        except Exception as e:
                            raise Exception(f"ERROR: {e}")
                        
                        try:
                            off = connectWires(firstWire_L, secondWire_L, ileft)
                        except Exception as e:
                            # p = Part.show(Part.Vertex(ileft[0]), "Trim point")
                            # p.ViewObject.PointSize = 6
                            # Part.show(firstWire_L, "first wire")
                            # Part.show(secondWire_L, "second wire")
                            # print(f"Failed to trim wire. Info: {ileft}")
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
                            # p = Part.show(Part.Vertex(iright[0]), "Trim point")
                            # p.ViewObject.PointSize = 6
                            # Part.show(firstWire_R, "first wire")
                            # Part.show(secondWire_R, "second wire")
                            # print(f"Failed to trim wire. Info: {iright}")
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
                        
                        feed_overrides.append(edge.getFeedOverride())
                else:
                    feed_overrides.append(1.0)

            if len(feed_overrides) != len(obj.Data):
                raise Exception("ERROR: Feed overrides calculation error.")
            
            obj.Offset_L = resultPoints_L
            obj.Offset_R = resultPoints_R
            obj.Pauses = pauses
            obj.PausesDurations = pausesDuration
            obj.RouteBreaks = breaks
            obj.FeedOverrides = feed_overrides

            obj.Redraw += 1 #change of this property will trigger VP to redraw
        except Exception as e:
            FreeCAD.Console.PrintError(f"Route {obj.Label} {e}\n")
            raise

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

class WireRouteVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    
    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        
        self.node = coin.SoGroup()

        self.drawRoute()
        obj.addDisplayMode(self.node, "Flat Lines")
        setPickStyle(obj, UNPICKABLE)

    def drawRoute(self):        
        if self.Object.Offset_L is not None and self.Object.Offset_R is not None and len(self.Object.Offset_L) > 0 and len(self.Object.Offset_R) > 0:
            while self.node.getNumChildren() > 0:
                self.node.removeChild(0)

            self.node.addChild(self.drawRouteLines(self.Object.Offset_L, self.Object.RouteBreaks))
            self.node.addChild(self.drawRouteLines(self.Object.Offset_R, self.Object.RouteBreaks))

            if self.Object.Pauses is not None and len(self.Object.Pauses) > 0 and len(self.Object.Pauses) == len(self.Object.PausesDurations):
                pauses = []
                for dur_idx, idx in enumerate(self.Object.Pauses):
                    dur = self.Object.PausesDurations[dur_idx]
                    pauses.append([self.Object.Offset_L[idx], float(dur)])
                    pauses.append([self.Object.Offset_R[idx], float(dur)])

                self.node.addChild(self.drawPauses(pauses))

    def drawPauses(self, points):
        group = coin.SoGroup()
        if len(points) > 0:
            color = coin.SoBaseColor()
            color.rgb.setValue(1, 0, 0)
            draw_style = coin.SoDrawStyle()
            draw_style.style = coin.SoDrawStyle.FILLED
            draw_style.lineWidth = 1
            group.addChild(draw_style)
            group.addChild(color)

            # points is array of pauses each item is also array, where first element is point coordinates and second is pause duration
            for i in range(len(points)):
                sep = coin.SoSeparator()                
               
                # Define the coordinates of the circle
                coords = coin.SoCoordinate3()
                num_segments = 20
                radius = points[i][1]
                circle_coords = []
                for idx in range(num_segments):
                    angle = 2.0 * math.pi * idx / num_segments
                    x = radius * math.cos(angle)
                    y = radius * math.sin(angle)
                    circle_coords.append((x, y, 0))
                coords.point.setValues(0, num_segments, circle_coords)
                
                faceSet = coin.SoFaceSet()
                faceSet.numVertices.setValue(num_segments)
                
                point = points[i][0]
                transform = coin.SoTransform()
                transform.translation.setValue(point.x, point.y, point.z)

                rotation = coin.SbRotation(coin.SbVec3f(0, 1, 0), math.radians(90))
                transform.rotation.setValue(rotation)

                shapeHints = coin.SoShapeHints()
                shapeHints.vertexOrdering = coin.SoShapeHints.CLOCKWISE

                sep.addChild(coords)
                sep.addChild(transform)
                sep.addChild(shapeHints)
                sep.addChild(faceSet)

                group.addChild(sep)

        return group

    def drawRouteLines(self, points, breaks):
        group = coin.SoGroup()
        if len(points) > 0:
            pointGroups = []

            if len(breaks) > 0:
                lastBreak = 0
                for idx in breaks:
                    pointGroups.append(points[lastBreak:idx + 1:1])
                    lastBreak = idx + 1
                if lastBreak < len(points) - 1:
                    pointGroups.append(points[lastBreak:])
            else:
                pointGroups.append(points)
            
            for pg in pointGroups:
                group.addChild(self.drawRouteLine(pg))
        return group
    
    """ def drawRouteLine(self, points):
        sep = coin.SoSeparator()
        if len(points) > 0:            
            p = coin.SoPointSet()
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, [[p.x, p.y, p.z] for p in points])
            color = coin.SoBaseColor()
            color.rgb.setValue(1, 0, 0)
            draw_style = coin.SoDrawStyle()
            draw_style.style = coin.SoDrawStyle.FILLED
            draw_style.pointSize = 2
            sep.addChild(draw_style)
            sep.addChild(color)
            sep.addChild(coords)
            sep.addChild(p)
        return sep """
    
    def drawRouteLine(self, points):
        sep = coin.SoSeparator()
        if len(points) > 0:            
            line = coin.SoLineSet()
            line.numVertices.setValue(len(points))
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, [[p.x, p.y, p.z] for p in points])
            color = coin.SoBaseColor()
            color.rgb.setValue(1, 0, 0)
            draw_style = coin.SoDrawStyle()
            draw_style.style = coin.SoDrawStyle.FILLED
            draw_style.lineWidth = 2
            sep.addChild(draw_style)
            sep.addChild(color)
            sep.addChild(coords)
            sep.addChild(line)
        return sep 
    
    def getIcon(self):
        return getIconPath("route.svg")

    def getDisplayModes(self, obj):
        """Return the display modes that this viewprovider supports."""
        return ["Flat Lines"]
    
    def claimChildren(self):
        return [object for object in self.Object.Objects]
    
    def onDelete(self, obj, subelements):
        group = App.ActiveDocument.getObject(self.Object.JobName)
        if group is not None and group.Type == "Job":
            for object in self.Object.Objects:
                group.addObject(object)
        return True
    
    def updateData(self, obj, prop):
        if prop == "Redraw":#prop == "Offset_L" or prop == "Offset_R" or prop == "Pauses" or prop == "PausesDurations":
            self.drawRoute()
        

class MakeRoute():
    """Make Route"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("route.svg"),
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create a route",
                "ToolTip" : "Create a route from selected objects."}

    def Activated(self):
        view = Gui.ActiveDocument.ActiveView
        doc = App.ActiveDocument
        group = view.getActiveObject("group")
        setActive = False

        # - if machine is not active, try to select first one in a document
        if group is None or group.Type != "Job":
            group = doc.getObject("Job")
            setActive = True

        if group is not None and group.Type == "Job":
            if setActive:
                view.setActiveObject("group", group)
            
            # - Get selecttion
            objects = [item.Object for item in Gui.Selection.getSelectionEx()]
            
            route = None
            try:
                # - Create object
                route = group.newObject("App::FeaturePython", "Route")
                WireRoute(route, objects, group.Name)
                WireRouteVP(route.ViewObject)

                for obj in objects:
                    #obj.ViewObject.Visibility = False
                    group.removeObject(obj)

                doc.recompute()
                Gui.Selection.clearSelection()
            except Exception as e:
                App.Console.PrintError(f"Failed to create route.\n")
                if route:
                    doc.removeObject(route.Name)
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":
                # - Get selected objects
                objects = [item.Object for item in Gui.Selection.getSelectionEx()]

                # - nothing selected
                if len(objects) == 0:
                    return False
                
                for obj in objects:
                    if not hasattr(obj, "Type") or obj.Type not in FC_TYPES_TO_ROUTE:
                        return False                    
                return True
            return False
            
Gui.addCommand("Route", MakeRoute())
