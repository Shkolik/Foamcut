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
from utilities import isMovement, isStraitLine, FC_KERF_DIRECTIONS, FC_KERF_STRATEGY, FC_ROUTE_KERF_DIRECTIONS
import pivy.coin as coin
import math

FC_KERF_STRATEGY_NONE = 0
FC_KERF_STRATEGY_UNI = 1
FC_KERF_STRATEGY_DYN = 2

SUPPRESS_WARNINGS = utilities.getParameterBool("SuppressWarnings", True)

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
        obj.Error = ""

        first       = obj.Objects[0]
        reversed    = None        # - Second segment is reversed
        START       = 0           # - Segment start point index
        END         = -1          # - Segment end point index
        route_data  = []
        route_data_dir  = []
        item_index  = 0

        # - Check is single element
        if len(obj.Objects) == 1:
            # - Store element            
            route_data.append(item_index)
            route_data_dir.append(False)

        # - Walk through other objects
        for second in obj.Objects[1:]:
            item_index += 1

            # - Process skipped element
            if first is None:
                first = second
                if first.Type == "Enter" and reversed is not None:
                    route_data.append(item_index)
                    route_data_dir.append(False)

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

                # - Store element
                route_data.append(item_index)
                route_data_dir.append(False)

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

                # - Store second element
                route_data.append(item_index)
                route_data_dir.append(reversed)
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

                # - Store next element
                route_data.append(item_index)
                route_data_dir.append(reversed)

            # - Go to next object
            first = second
        
        if len(route_data) != len(route_data_dir) or len(route_data) == 0:
            obj.Error("Error: Data calculation error.")
            App.Console.PrintError(obj.Error)
            return False
        
        obj.Data = route_data
        obj.DataDirection = route_data_dir

        pauses = []
        pausesDuration = []
        breaks = []
        
        # - try to make a offset       
        resultPoints_L = []
        resultPoints_R = []
        
        lastObjectPoint = 0

        if obj.KerfCompensation > 0 and FC_KERF_STRATEGY.index(obj.CompensationStrategy) > FC_KERF_STRATEGY_NONE:
            # list of (edges_l, edges_r, offset_len_L, offset_len_R, points_count)
            edgesGroups = []

            edges_L = []
            edges_R = []
            points_count = []

            offset_len_L =[]
            offset_len_R =[]

            lastObjectType = None

            for i in range(len(route_data)):
                if lastObjectType == "Rotation" or lastObjectType == "Exit":
                    breaks.append(lastObjectPoint)
                    edgesGroups.append((edges_L, edges_R, offset_len_L, offset_len_R, points_count))

                    edges_L = [] 
                    edges_R = []
                    points_count = []
                    offset_len_L =[]
                    offset_len_R =[]

                item = route_data[i]
                object = obj.Objects[item]
                lastObjectType = object.Type

                if lastObjectType == "Rotation":                                   
                    continue

                points_count.append(object.PointsCount)
                lastObjectPoint += object.PointsCount - 1

                idx = FC_KERF_DIRECTIONS.index(object.CompensationDirection) if object.CompensationDirection in FC_KERF_DIRECTIONS else 0
                
                dir = -1 * (idx - 1) if obj.CompensationDirection in FC_ROUTE_KERF_DIRECTIONS and FC_ROUTE_KERF_DIRECTIONS.index(obj.CompensationDirection) == 1 else idx - 1;
                
                #print("Offset dir: {}".format(dir))

                path_l = object.Path_L[::-1] if route_data_dir[i] else object.Path_L
                path_r = object.Path_R[::-1] if route_data_dir[i] else object.Path_R

                leftEdgeLen = float(object.LeftEdgeLength) if object.LeftEdgeLength > 0 else 0.1
                rightEdgeLen = float(object.RightEdgeLength) if object.RightEdgeLength > 0 else 0.1

                leftSegmentLen = float(object.LeftSegmentLength) if object.LeftSegmentLength > 0 else 0.1
                rightSegmentLen = float(object.RightSegmentLength) if object.RightSegmentLength > 0 else 0.1

                len_l = float(obj.KerfCompensation) * dir
                len_r = float(obj.KerfCompensation) * dir

                if dir != 0 and FC_KERF_STRATEGY.index(obj.CompensationStrategy) == FC_KERF_STRATEGY_DYN:
                    #calculate compensation for edges
                    dEdges = leftEdgeLen/rightEdgeLen # if dEdges > 1 then left longer

                    dLeft =  leftEdgeLen/leftSegmentLen if dEdges > 1 else leftEdgeLen/rightSegmentLen# if > 1 -> left segment longer than edge
                    dRight = rightEdgeLen/leftSegmentLen if dEdges > 1 else rightEdgeLen/rightSegmentLen # if > 1 -> right segment longer than edge
                    
                    left_c = 1.0 
                    right_c = 1.0

                    if obj.CompensationDegree > 0 and not math.isclose(leftEdgeLen, rightEdgeLen, rel_tol=5e-2): #if degree is specified and edges length difference more that 5%  
                        left_c = obj.CompensationDegree if dEdges < 1 else left_c
                        right_c = right_c if dEdges < 1 else obj.CompensationDegree

                    len_l = len_l/(float(dLeft) * left_c)
                    len_r = len_r/(float(dRight) * right_c)

                edges_L.append(self.makeWire(path_l))
                edges_R.append(self.makeWire(path_r))

                offset_len_L.append(len_l)
                offset_len_R.append(len_r)

                if hasattr(object, "AddPause") and object.AddPause:
                    pauses.append(lastObjectPoint)
                    pausesDuration.append(float(object.PauseDuration)) 
            
            if lastObjectType != "Rotation":
                edgesGroups.append((edges_L, edges_R, offset_len_L, offset_len_R, points_count))

            for (edges_L, edges_R, offset_len_L, offset_len_R, points_count) in edgesGroups:
                
                offsets_L = self.makeOffsets(offset_len_L, edges_L)
                offsets_R = self.makeOffsets(offset_len_R, edges_R)

                intersections_L = []
                intersections_R = []
                
                for i in range(len(offsets_L) - 1):                
                    ileft = self.intersectWires(offsets_L[i], offsets_L[i + 1])
                    iright = self.intersectWires(offsets_R[i], offsets_R[i + 1])
                    intersections_L.append(ileft)
                    intersections_R.append(iright)
                                
                firstWire = None
                for i in range(len(offsets_L) - 1):
                    if firstWire == None:
                        firstWire = offsets_L[i]
                        
                    off = self.fixOffsets(firstWire, offsets_L[i + 1], intersections_L[i])
                    
                    if off == None:
                        App.Console.PrintError("ERROR: LEFT OFFSET Something wrong near point: {}; idx: {}".format(intersections_L[i], i))
                    
                    # - discretize wire so it will have same count of vertices as source wire
                    firstWirePoints = self.getWirepoints(off[0], points_count[i])
                    for pi in range(len(firstWirePoints) - 1):
                        resultPoints_L.append(firstWirePoints[pi])
                    
                    firstWire = off[1]

                lastWirePoints = self.getWirepoints(firstWire if firstWire is not None else offsets_L[-1], points_count[-1])
                for p in lastWirePoints:
                    resultPoints_L.append(p)

                firstWire = None
                for i in range(len(offsets_R) - 1):
                    if firstWire == None:
                        firstWire = offsets_R[i]
                        
                    off = self.fixOffsets(firstWire, offsets_R[i + 1], intersections_R[i])
                    
                    if off == None:
                        print("ERROR: RIGHT OFFSET Something wrong near point: {}; idx: {}".format(intersections_R[i], i))
                    
                    # - discretize wire so it will have same count of vertices as source wire
                    firstWirePoints = self.getWirepoints(off[0], points_count[i])
                    for pi in range(len(firstWirePoints) - 1):
                        resultPoints_R.append(firstWirePoints[pi])
                        
                    firstWire = off[1]

                lastWirePoints = self.getWirepoints(firstWire if firstWire is not None else offsets_R[-1], points_count[-1])
                for p in lastWirePoints:
                    resultPoints_R.append(p)            
        else:  
            points_count = []

            for i in range(len(route_data)):                                
                # - Access item
                item = route_data[i]

                object = obj.Objects[item]

                if object.Type == "Rotation":
                    breaks.append(lastObjectPoint)
                    continue

                points_count.append(object.PointsCount)
                lastObjectPoint += object.PointsCount - 1

                if hasattr(object, "AddPause") and object.AddPause:
                    pauses.append(lastObjectPoint)
                    pausesDuration.append(float(object.PauseDuration)) 

                path_l = object.Path_L[::-1] if route_data_dir[i] else object.Path_L
                path_r = object.Path_R[::-1] if route_data_dir[i] else object.Path_R

                if len(path_l) == object.PointsCount:
                    for idx in range(len(path_l) - 1):
                        resultPoints_L.append(path_l[idx])
                else:
                    wire = self.makeWire(path_l)
                    points = self.getWirepoints(wire, object.PointsCount)
                    for idx in range(len(points) - 1):
                        resultPoints_L.append(points[idx])
                if len(path_r) == object.PointsCount:
                    for idx in range(len(path_r) - 1):
                        resultPoints_R.append(path_r[idx])
                else:
                    wire = self.makeWire(path_r)
                    points = self.getWirepoints(wire, object.PointsCount)
                    for idx in range(len(points) - 1):
                        resultPoints_R.append(points[idx])
                
                if i == len(route_data) - 1:
                    resultPoints_L.append(path_l[-1])
                    resultPoints_R.append(path_r[-1])

        obj.Offset_L = resultPoints_L
        obj.Offset_R = resultPoints_R
        obj.Pauses = pauses
        obj.PausesDurations = pausesDuration
        obj.RouteBreaks = breaks

        obj.Redraw += 1 #change of this property will trigger VP to redraw

    def makeWire(self, points):
        ''' 
        Create wire from list of points

        @param points - list of points
        '''
        edges = []
        for i in range(len(points) - 1):
            edges.append(Part.LineSegment(points[i], points[i+1]))    
        return Part.Wire([edge.toShape() for edge in edges])
    
    def makeLineOffset(self, wire, offset):
        '''
        Create offset wire
        
        @param wire - source wire (should be strait line, only start and end vertices will be used)
        @param offset - distance to offset, where: negative - offset to the left; 0 - no offset; positive - offset to the right.
        
        @return offset wire
        '''
        start = wire.Vertexes[0].Point
        end = wire.Vertexes[-1].Point
        
        direction = end - start
        direction.normalize()
        
        perpendicular = direction.cross(App.Vector(1,0,0))
        perpendicular.normalize()
        
        res_start = start + float(offset) * perpendicular
        res_end = end + float(offset) * perpendicular
        
        return Part.Wire(Part.LineSegment(res_start, res_end).toShape())
    
    def makeOffset(self, offset, source):
        '''
        Create offset wire

        @param offset - distance to offset, where: negative - offset to the left; 0 - no offset; positive - offset to the right.
        @param source = source wire
        @returns offset wire
        '''

        if offset == 0:
            return source
        
        if isStraitLine(source): # strait line     
            wire = self.makeLineOffset(source, offset)                
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
                    wires.append(self.makeLineOffset(edge, offset))
                
                intersections = []
                for i in range(len(wires) - 1):                
                    intersections.append(self.intersectWires(wires[i], wires[i + 1]))

                points = []
                firstWire = None
                for i in range(len(wires) - 1):
                    if firstWire == None:
                        firstWire = wires[i]
                        
                    (first, second) = self.fixOffsets(firstWire, wires[i + 1], intersections[i])
                    
                    for vi in range(len(first.Vertexes) - 1):
                        points.append(first.Vertexes[vi].Point)
                        
                    firstWire = second

                if firstWire is None:
                    firstWire = wires[-1]
                
                for v in firstWire.Vertexes:
                        points.append(v.Point)
                wire = self.makeWire(points)

        return wire

    def makeOffsets(self, offset, wires):
        '''
        create offsetted wires 
        @param offset - list of distances to offset, where: < 0 - offset to the left; 0 - no offset; > 0 - offset to the right.
        @param wires - list of source wires
        @return list of wires
        '''
        offsets = []
        for i, wire in enumerate(wires): 
            offsets.append(self.makeOffset(offset[i], wire))

        return offsets
    
    def intersectWires(self, wire1, wire2, tolerance = 1e-4):
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

                L1_end = wire1.Edges[-1]
                L2_start = wire2.Edges[0]
                res = L1_end.Curve.intersectCC(L2_start.Curve)

                if len(res) == 0:
                    # wires are parallel but endpoints close togeter withing tolerance
                    if math.isclose(0.0, dist, abs_tol=tolerance):                        
                        return (v1, 0)
                    else:                                         
                        message = "Wires not intersect. Check offset direction. Distance between edges = {}".format(dist)
                        raise Exception(message)
                else:
                    intPoint = App.Vector(res[0].X, res[0].Y, res[0].Z)

                    int_L1_start = intPoint.distanceToPoint(wire1.Edges[0].Vertexes[0].Point)
                    int_L1_end = intPoint.distanceToPoint(L1_end.Vertexes[-1].Point)
                    int_L2_start = intPoint.distanceToPoint(L2_start.Vertexes[0].Point)
                    int_L2_end = intPoint.distanceToPoint(L2_start.Vertexes[0].Point)

                    # check where intersection located. If it's on other end of any wire then we have almost parallel lines
                    # and proper offset intersection will not work. 
                    # We assyme that it's better to place inersection point somewhere close to the end of one of the wires 
                    # than throw an error
                    # TODO: Think about better solution for this situation
                    if dist > 0 and (int_L1_end > int_L1_start or int_L2_start > int_L2_end): 
                        wire = wire1 if int_L1_end > int_L1_start else wire2
                        end = int_L1_end > int_L1_start 

                        if len(wire.Edges) == 1:
                            dir = wire.Edges[0].Vertexes[-1].Point.sub(wire.Edges[0].Vertexes[0].Point) if end else wire.Edges[0].Vertexes[0].Point.sub(wire.Edges[0].Vertexes[-1].Point)
                            dir.normalize()
                            intPoint = wire.Edges[0].Vertexes[-1].Point - dir*dist if end else wire.Edges[0].Vertexes[0].Point + dir*dist#wire.Edges[0].CenterOfMass
                        else:
                            intPoint = wire.Vertexes[1].Point
                        if not SUPPRESS_WARNINGS:
                            App.Console.PrintWarning(
"Intersection point too far from ideal position or not exists. \r\n \
It happens when 2 connected paths has too different compensation. \r\n \
Check route for any logical errors, try another kerf compensation strategy or rethink paths set if result not pleasant. \r\n")    
                
                return (intPoint, 1)
    
    def fixOffsets(self, o1_wire, o2_wire, intersection):
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
                wire1 = self.makeWire(points)
            else:            
                wire1 = self.trimWireEnd(o1_wire, index2, point)
            
            (topo1, index1, param1, topo2, index2, param2) = infos2[0]
            # intersection is outside. We need to add one more edge to offset
            if dist1 > 0 and topo2 == "Vertex": 
                points = [point] + [v.Point for v in o2_wire.Vertexes]
                wire2 = self.makeWire(points)
            else:
                wire2 = self.trimWireStart(o2_wire, index2, point)
                
            return [wire1, wire2]
        if tp == 2:
            (dist, vectors, infos) = o1_wire.distToShape(o2_wire)
            (topo1, index1, param1, topo2, index2, param2) = infos[0]
                    
            #trim first wire
            wire1 = self.trimWireEnd(o1_wire, index1, point)
            #trim second wire
            wire2 = self.trimWireStart(o2_wire, index2, point)
            return [wire1, wire2]
        return None
    
    def trimWireEnd(self, wire, index, point):
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
    
    def trimWireStart(self, wire, index, point):
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
        #bs.approximate(Points = [v.Point for v in wire.Vertexes], Continuity="C0")
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
