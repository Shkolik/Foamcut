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
import utilities
from utilities import isMovement, isStraitLine, getWorkingPlanes, FC_KERF_DIRECTIONS, FC_KERF_STRATEGY, FC_ROUTE_KERF_DIRECTIONS
import pivy.coin as coin
import math
import time

FC_KERF_STRATEGY_NONE = 0
FC_KERF_STRATEGY_UNI = 1
FC_KERF_STRATEGY_DYN = 2

SUPPRESS_WARNINGS = utilities.getParameterBool("SuppressWarnings", True)

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

        self.ObjectType = None

    def projectToPlanes(self, leftPlane, rightPlane):
        projectedLeft = []
        projectedRight = []

        for i in range(len(self.PointsLeft)):
            projectedLeft.append(utilities.intersectLineAndPlane(self.PointsLeft[i], self.PointsRight[i], leftPlane))
            projectedRight.append(utilities.intersectLineAndPlane(self.PointsLeft[i], self.PointsRight[i], rightPlane))

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
        feed_override = 1.0
        if dynamic:
            #calculate compensation for the sides
            dEdges = self.LeftEdgeLength/self.RightEdgeLength # if dEdges > 1 then left longer

            left_c = 1.0 if dEdges > 1 else self.RightEdgeLength/self.LeftEdgeLength # if > 1 -> left edge gets nominal kerf, else more
            right_c = 1.0 if dEdges < 1 else self.LeftEdgeLength/self.RightEdgeLength # if > 1 -> right edge gets nominal kerf, else more

            if degree > 0 and not math.isclose(self.LeftEdgeLength, self.RightEdgeLength, rel_tol=1e-1): #if degree is specified and edges length difference more that 10%  
                 left_c = left_c / degree if dEdges < 1 else left_c
                 right_c = right_c / degree if dEdges > 1 else right_c

            self.OffsetLenLeft = self.OffsetLenLeft * left_c
            self.OffsetLenRight = self.OffsetLenRight * right_c

            feed_override = self.LeftSegmentLength/self.LeftEdgeLength if dEdges > 1 else self.RightSegmentLength/self.RightEdgeLength 
            print("Feed override: {}".format(feed_override))
            # print("Left offset: {}, Right offset: {}".format(self.OffsetLenLeft, self.OffsetLenRight))
            # dLeft =  self.LeftEdgeLength/self.LeftSegmentLength if dEdges > 1 else self.LeftEdgeLength/self.RightSegmentLength # if > 1 -> left segment longer than edge
            # dRight = self.RightEdgeLength/self.LeftSegmentLength if dEdges > 1 else self.RightEdgeLength/self.RightSegmentLength # if > 1 -> right segment longer than edge
            
            # left_c = 1.0 
            # right_c = 1.0

            # if degree > 0 and not math.isclose(self.LeftEdgeLength, self.RightEdgeLength, rel_tol=5e-2): #if degree is specified and edges length difference more that 5%  
            #     left_c = degree if dEdges < 1 else left_c
            #     right_c = right_c if dEdges < 1 else degree

            # self.OffsetLenLeft = self.OffsetLenLeft/(float(dLeft) * left_c)
            # self.OffsetLenRight = self.OffsetLenRight/(float(dRight) * right_c)

        lWire = utilities.makeWireOffset(utilities.makeWire(self.PointsLeft), self.OffsetLenLeft)
        rWire = utilities.makeWireOffset(utilities.makeWire(self.PointsRight), self.OffsetLenRight)        
        self.OffsetLeft = [v.Point for v in lWire.Vertexes]
        self.OffsetRight = [v.Point for v in rWire.Vertexes]

        if dynamic:            
            Part.show(lWire, "Left Offset")
            Part.show(rWire, "Right Offset")

        return feed_override


class WireRoute(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, objects, jobName):   
        super().__init__(obj, jobName)     
        obj.Type = "Route"  
        
        obj.addProperty("App::PropertyString",      "Error",            "", "", 5) 

        obj.addProperty("App::PropertyVectorList",  "Offset_L",         "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Offset_R",         "", "", 5)

        obj.addProperty("App::PropertyIntegerList", "RouteBreaks",      "", "", 5) # indexes of a points where route breaks - Rotation

        obj.addProperty("App::PropertyIntegerList", "Pauses",           "", "", 5) # indexes of a points where should be pause
        obj.addProperty("App::PropertyFloatList",   "PausesDurations",  "", "", 5) 

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

        if touched:
            obj.recompute()

    def execute(self, obj):
        start_time = time.perf_counter()

        obj.Error = ""

        config = self.getConfig(obj)

        doc = obj.Document

        job = doc.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            App.Console.PrintError("ERROR:\n Error updating Enter - active Job not found\n")

        (wpl, wpr) = getWorkingPlanes(job, doc)

        first       = obj.Objects[0]
        reversed    = None        # - Second segment is reversed
        START       = 0           # - Segment start point index
        END         = -1          # - Segment end point index
        route_data  = []
        route_data_dir  = []
        route_feed_overrides = []
        item_index  = 0

        pauses = []
        pausesDuration = []
        breaks = []

        lastObjectPoint = 0

        # - Check is single element
        if len(obj.Objects) == 1:
            # - Store element            
            route_data.append(item_index)
            route_data_dir.append(False)
            route_feed_overrides.append(1.0)
            object = obj.Objects[item_index]

            lastObjectPoint = object.PointsCount - 1

            if hasattr(object, "AddPause") and object.AddPause:
                pauses.append(lastObjectPoint)
                pausesDuration.append(float(object.PauseDuration))

        # - Walk through other objects
        for second in obj.Objects[1:]:
            item_index += 1

            # - Process skipped element
            if first is None:
                first = second
                if first.Type == "Enter" and reversed is not None:
                    route_data.append(item_index)
                    route_data_dir.append(False)
                    route_feed_overrides.append(1.0)
                    lastObjectPoint += first.PointsCount - 1

                    if hasattr(first, "AddPause") and first.AddPause:
                        pauses.append(lastObjectPoint)
                        pausesDuration.append(float(first.PauseDuration))

                #print("SKIP: %s" % second.Type)               
                continue
            
            if first.Type == "Projection" and first.PointsCount < 2:
                print("Vertex Projection - skip")
                first = second
                continue

            # - Skip rotation object
            if first.Type == "Rotation":
                #print("R1")
                # - Store first element
                route_data.append(item_index - 1)
                route_data_dir.append(False)
                route_feed_overrides.append(1.0)
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
                route_feed_overrides.append(1.0)
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
                    route_feed_overrides.append(1.0)

                    lastObjectPoint += first.PointsCount - 1

                    if hasattr(first, "AddPause") and first.AddPause:
                        pauses.append(lastObjectPoint)
                        pausesDuration.append(float(first.PauseDuration))

                # - Store element
                route_data.append(item_index)
                route_data_dir.append(False)
                route_feed_overrides.append(1.0)

                breaks.append(lastObjectPoint)

                lastObjectPoint += second.PointsCount - 1

                if hasattr(second, "AddPause") and second.AddPause:
                    pauses.append(lastObjectPoint)
                    pausesDuration.append(float(second.PauseDuration))

                first = second
                reversed = False # enter always normal
                continue
            
            # - Get lines on left plane
            if isMovement(first) or first.Type == "Enter":
                first_line  = first.Path_L
            else:
                obj.Error = "ERROR: {} - Unsupported first element. Second = {}".format(first.Label, second.Label)
                App.Console.PrintError(obj.Error)
                return False
            
            if isMovement(second) or second.Type == "Exit": 
                second_line = second.Path_L
            else:
                obj.Error = "ERROR: {} - Unsupported second element. First = {}".format(second.Label, first.Label)
                App.Console.PrintError(obj.Error)
                return False
            
            if reversed is None:
                first_reversed = False
                
                # - Detect first pair
                if utilities.isCommonPoint(first_line[END], second_line[START]):
                    #print ("First connected: FWD - FWD")
                    reversed = False
                elif utilities.isCommonPoint(first_line[END], second_line[END]):
                    #print ("First connected: FWD - REV")
                    reversed = True
                elif utilities.isCommonPoint(first_line[START], second_line[START]):
                    #print ("First connected: REV - FWD")
                    first_reversed  = True
                    reversed        = False
                elif utilities.isCommonPoint(first_line[START], second_line[END]):
                    #print ("First connected: REV - REV")
                    first_reversed  = True
                    reversed        = True
                else:
                    obj.Error = "ERROR: {} not connected with {}".format(first.Label, second.Label)
                    App.Console.PrintError(obj.Error)
                    return False
                
                # - Store first element
                route_data.append(item_index - 1)
                route_data_dir.append(first_reversed)
                route_feed_overrides.append(1.0)

                lastObjectPoint += first.PointsCount - 1

                if hasattr(first, "AddPause") and first.AddPause:
                    pauses.append(lastObjectPoint)
                    pausesDuration.append(float(first.PauseDuration))

            else:                
                # - Detect next pairs
                if utilities.isCommonPoint(first_line[START if reversed else END], second_line[START]):
                    #print ("Connected: FWD - FWD")
                    reversed = False
                elif utilities.isCommonPoint(first_line[START if reversed else END], second_line[END]):
                    #print ("Connected: FWD - REV")
                    reversed = True
                else:
                    obj.Error = "ERROR: {} not connected with {}".format(first.Label, second.Label)
                    App.Console.PrintError(obj.Error)
                    return False

            # - Store second element
            route_data.append(item_index)
            route_data_dir.append(reversed)
            route_feed_overrides.append(1.0)

            lastObjectPoint += second.PointsCount - 1

            if hasattr(second, "AddPause") and second.AddPause:
                pauses.append(lastObjectPoint)
                pausesDuration.append(float(second.PauseDuration))

            # - Go to next object
            first = second
        
        if len(route_data) != len(route_data_dir) or len(route_data) == 0:
            obj.Error("Error: Data calculation error.")
            App.Console.PrintError(obj.Error)
            return False
        
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

            currentEdge.ObjectType = object.Type
            currentEdge.PointsCount = object.PointsCount
            currentEdge.CompensationDirection = object.CompensationDirection

            currentEdge.LeftEdgeLength = float(object.LeftEdgeLength) if object.LeftEdgeLength > 0 else 0.1
            currentEdge.RightEdgeLength = float(object.RightEdgeLength) if object.RightEdgeLength > 0 else 0.1

            currentEdge.LeftSegmentLength = float(object.LeftSegmentLength) if object.LeftSegmentLength > 0 else 0.1
            currentEdge.RightSegmentLength = float(object.RightSegmentLength) if object.RightSegmentLength > 0 else 0.1

            currentEdge.PointsLeft = object.Path_L[::-1] if route_data_dir[i] else object.Path_L
            currentEdge.PointsRight = object.Path_R[::-1] if route_data_dir[i] else object.Path_R
            currentSegment.LastPoint += object.PointsCount - 1

            if hasattr(object, "AddPause") and object.AddPause:
                pauses.append(currentSegment.LastPoint)
                pausesDuration.append(float(object.PauseDuration)) 

            if not currentSegment.SimpleProjection:
                if object.Type == "Projection":
                    currentSegment.SimpleProjection = True
                else:
                    (left, right) = self.getEdges(object)
                    currentSegment.LeftPlaneX = left.BoundBox.XMin if left.BoundBox.XMin < currentSegment.LeftPlaneX else currentSegment.LeftPlaneX
                    currentSegment.RightPlaneX = right.BoundBox.XMax if right.BoundBox.XMax > currentSegment.RightPlaneX else currentSegment.RightPlaneX

            currentSegment.Edges.append(currentEdge)

        if currentEdge.ObjectType != "Rotation":
            segments.append(currentSegment)

        applyKerf = obj.KerfCompensation > 0 and FC_KERF_STRATEGY.index(obj.CompensationStrategy) > FC_KERF_STRATEGY_NONE

        # apply kerf compensation if needed
        if applyKerf:
            # build temporary planes for projection
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
                
                for j in range(len(segment.Edges) - 1):
                    edge = segment.Edges[j]
                    if firstWire_L == None and firstWire_R == None:
                        firstWire_L = utilities.makeWire(edge.OffsetLeft)
                        firstWire_R = utilities.makeWire(edge.OffsetRight)
                    
                    if secondWire_L == None and secondWire_R == None:
                        secondWire_L = utilities.makeWire(segment.Edges[j + 1].OffsetLeft)
                        secondWire_R = utilities.makeWire(segment.Edges[j + 1].OffsetRight)

                    ileft = utilities.intersectWires(firstWire_L, secondWire_L, tolerance=5e-2)
                    iright = utilities.intersectWires(firstWire_R, secondWire_R, tolerance=5e-2)

                    off = utilities.connectWires(firstWire_L, secondWire_L, ileft)
                    
                    if off == None:
                        App.Console.PrintError("ERROR: LEFT OFFSET Something wrong near point: {}; idx: {}".format(ileft, j))
                    
                    # - discretize wire so it will have same count of vertices as source wire
                    edge.OffsetLeft = self.getWirepoints(off[0], edge.PointsCount)

                    firstWire_L = off[1]
                    secondWire_L = None

                    off = utilities.connectWires(firstWire_R, secondWire_R, iright)
                    
                    if off == None:
                        App.Console.PrintError("ERROR: RIGHT OFFSET Something wrong near point: {}; idx: {}".format(iright, j))
                    
                    # - discretize wire so it will have same count of vertices as source wire
                    edge.OffsetRight = self.getWirepoints(off[0], edge.PointsCount)

                    firstWire_R = off[1]
                    secondWire_R = None

                    if not segment.SimpleProjection:
                        left_Off = []
                        right_off = []
                        for p in range(edge.PointsCount):
                            left_Off.append(utilities.intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpl))
                            right_off.append(utilities.intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpr))
                        edge.OffsetLeft = left_Off
                        edge.OffsetRight = right_off

                # add last edge points
                edge = segment.Edges[-1]
                if firstWire_L is not None and firstWire_R is not None:                  
                    edge.OffsetLeft = self.getWirepoints(firstWire_L, edge.PointsCount)
                    edge.OffsetRight = self.getWirepoints(firstWire_R, edge.PointsCount)

                if not segment.SimpleProjection:
                    left_Off = []
                    right_off = []
                    for p in range(edge.PointsCount):                            
                        left_Off.append(utilities.intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpl))
                        right_off.append(utilities.intersectLineAndPlane(edge.OffsetLeft[p], edge.OffsetRight[p], wpr))
                    edge.OffsetLeft = left_Off
                    edge.OffsetRight = right_off

        # build route from segments and edges
        for i, segment in enumerate(segments):
            for j, edge in enumerate(segment.Edges):
                for idx in range(edge.PointsCount - 1):
                    resultPoints_L.append(edge.OffsetLeft[idx] if applyKerf else edge.PointsLeft[idx])
                    resultPoints_R.append(edge.OffsetRight[idx] if applyKerf else edge.PointsRight[idx])
                
                # add last point of the last edge
                if j == len(segment.Edges) - 1:
                    resultPoints_L.append(edge.OffsetLeft[-1] if applyKerf else edge.PointsLeft[-1])
                    resultPoints_R.append(edge.OffsetRight[-1] if applyKerf else edge.PointsRight[-1])

        obj.Offset_L = resultPoints_L
        obj.Offset_R = resultPoints_R
        obj.Pauses = pauses
        obj.PausesDurations = pausesDuration
        obj.RouteBreaks = breaks

        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        print("Elapsed time: {} seconds".format(elapsed_time))

        obj.Redraw += 1 #change of this property will trigger VP to redraw

    def getWirepoints(self, wire, num_points):
        '''
        Make a Bspline from wire, discretize it with specified number of points
        @param wire - wire to discretize
        @param num_points - number of points
        @return list of points 
        '''
        if num_points <= 2: # short strait line - no need to convert
            return [wire.Vertexes[0].Point, wire.Vertexes[-1].Point]
        
        bs = Part.BSplineCurve()
        bs.interpolate([v.Point for v in wire.Vertexes])
        res = bs.discretize(Number=num_points)
        
        return res
    

class WireRouteVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    
    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        
        self.node = coin.SoGroup()

        self.drawRoute()
        obj.addDisplayMode(self.node, "Flat Lines")
        utilities.setPickStyle(obj, utilities.UNPICKABLE)

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
        return utilities.getIconPath("route.svg")

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
        return {"Pixmap"  : utilities.getIconPath("route.svg"),
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create a route",
                "ToolTip" : "Create a route from selected objects."}

    def Activated(self): 
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        setActive = False
        # - if machine is not active, try to select first one in a document
        if group is None or group.Type != "Job":
            group = App.ActiveDocument.getObject("Job")
            setActive = True

        if group is not None and group.Type == "Job":
            if setActive:
                Gui.ActiveDocument.ActiveView.setActiveObject("group", group)
            
            # - Get selecttion
            objects = [item.Object for item in Gui.Selection.getSelectionEx()]
            
            # - Create object
            route = group.newObject("App::FeaturePython", "Route")
            WireRoute(route, objects, group.Name)
            WireRouteVP(route.ViewObject)

            for obj in objects:
                #obj.ViewObject.Visibility = False
                group.removeObject(obj)

            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()
    
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
                    if not hasattr(obj, "Type") or obj.Type not in utilities.FC_TYPES_TO_ROUTE:
                        return False                    
                return True
            return False
            
Gui.addCommand("Route", MakeRoute())
