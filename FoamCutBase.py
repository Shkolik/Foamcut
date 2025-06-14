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

class FoamCutBaseObject:
    """FoamCut base object"""

    def __init__(self, obj, jobName):
        obj.addProperty("App::PropertyString",    "Type", "", "", 5)
        obj.addProperty("App::PropertyString",    "JobName", "", "", 5).JobName = jobName

        if hasattr(obj, "Placement"):
            obj.setEditorMode("Placement", 3)

    def getConfigName(self, obj):
        job = obj.Document.getObject(obj.JobName)

        if job is None:
            App.Console.PrintError("ERROR:\n Job with name '{}' not found in active document.\n".format(obj.JobName))
                
        return job.ConfigName
    
    def getConfig(self, obj):
        job = App.ActiveDocument.getObject(obj.JobName)

        if job is None:
            App.Console.PrintError("ERROR:\n Job with name '{}' not found in active document.\n".format(obj.JobName))
                
        return job.getObject(job.ConfigName)

class FoamCutMovementBaseObject(FoamCutBaseObject):
    def __init__(self, obj, jobName):
        super().__init__(obj, jobName)  
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
        obj.addProperty("App::PropertyTime",        "PauseDuration",        "Task", "Pause duration seconds")

        obj.addProperty("App::PropertyEnumeration", "CompensationDirection", "Kerf Compensation",   "Kerf compensation direction").CompensationDirection = FC_KERF_DIRECTIONS
        obj.CompensationDirection = 0 # Normal compensation by default


        config = self.getConfigName(obj)
        obj.setExpression(".DiscretizationStep", u"<<{}>>.DiscretizationStep".format(config))
        obj.setExpression(".PauseDuration", u"<<{}>>.PauseDuration".format(config))

        obj.setEditorMode("PauseDuration", 3)

    def onDocumentRestored(self, obj):
        touched = False   
        # Migrating from 0.1.2 to 0.1.3 - this properties needed for dynamic kerf compensation
        if not hasattr(obj, "LeftEdgeLength"):
            obj.addProperty("App::PropertyDistance",    "LeftEdgeLength",     "", "", 5)   
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding LeftEdgeLength property.".format(obj.Label))
            touched = True
        if not hasattr(obj, "RightEdgeLength"):
            obj.addProperty("App::PropertyDistance",    "RightEdgeLength",     "", "", 5)
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding RightEdgeLength property.".format(obj.Label))  
            touched = True
        if hasattr(obj, "KerfCompensationDirection"):
            dir = FC_KERF_DIRECTIONS.index(obj.KerfCompensationDirection) if obj.KerfCompensationDirection in FC_KERF_DIRECTIONS else 0            
            obj.removeProperty("KerfCompensationDirection")
            print("{} - Migrating from 0.1.2 to 0.1.3 - removing KerfCompensationDirection property.".format(obj.Label))  
            touched = True
        if not hasattr(obj, "CompensationDirection"):
            obj.addProperty("App::PropertyEnumeration", "CompensationDirection", "Kerf Compensation",   "Kerf compensation direction").CompensationDirection = FC_KERF_DIRECTIONS
            obj.CompensationDirection = dir
            print("{} - Migrating from 0.1.2 to 0.1.3 - adding CompensationDirection property.".format(obj.Label))  
            touched = True

        if touched:
            obj.recompute()

    def onChanged(self, obj, prop):        
        if prop == "AddPause":
            if obj.AddPause:
                obj.setEditorMode("PauseDuration", 0)
            else:
                obj.setEditorMode("PauseDuration", 3)
        return

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

    def findOppositeVertexes(self, obj, parent, vertex):
        oppositeVertex = None

        doc = obj.Document

        job = doc.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            App.Console.PrintError("ERROR:\n Error updating Enter - active Job not found\n")

        wp = getWorkingPlanes(job, doc)

        # check if selected vertex laying on any working plane
        onLeftPlane = wp[0].Shape.isInside(vertex.Point, 0.01, True)
        onRightPlane = wp[1].Shape.isInside(vertex.Point, 0.01, True)
        onPlane = onLeftPlane or onRightPlane

        isLeft = False

        # get edges or vertices on object we cut from parent action (move, join, path...)
        (left, right) = self.getEdges(parent)

        if onPlane:
            if isMovement(parent):
                
                point = vertex.Point
                (distToLeft, _, _) = vertex.distToShape(left)
                (distToRight, _, _) = vertex.distToShape(right)
                
                # - Connect
                if isCommonPoint(parent.Path_L[START], point):
                    isLeft = True
                    if distToLeft < distToRight:
                        vertex = left if isinstance(left, Part.Vertex) else left.firstVertex()
                        oppositeVertex = right if isinstance(right, Part.Vertex) else (right.firstVertex() if not parent.EdgesInverted else right.lastVertex())            
                    else:
                        vertex = right if isinstance(right, Part.Vertex) else right.firstVertex()
                        oppositeVertex = left if isinstance(left, Part.Vertex) else (left.firstVertex() if not parent.EdgesInverted else left.lastVertex())
                elif isCommonPoint(parent.Path_L[END], point):
                    isLeft = True
                    if distToLeft < distToRight:
                        vertex = left if isinstance(left, Part.Vertex) else left.lastVertex()
                        oppositeVertex = right if isinstance(right, Part.Vertex) else (right.lastVertex() if not parent.EdgesInverted else right.firstVertex())
                    else:
                        vertex = right if isinstance(right, Part.Vertex) else right.lastVertex()
                        oppositeVertex = left if isinstance(left, Part.Vertex) else (left.lastVertex() if not parent.EdgesInverted else left.firstVertex())
                elif isCommonPoint(parent.Path_R[START], point):
                    if distToRight < distToLeft:
                        vertex = right if isinstance(right, Part.Vertex) else right.firstVertex()
                        oppositeVertex = left if isinstance(left, Part.Vertex) else (left.firstVertex() if not parent.EdgesInverted else left.lastVertex())                
                    else:
                        vertex = left if isinstance(left, Part.Vertex) else left.firstVertex()
                        oppositeVertex = right if isinstance(right, Part.Vertex) else (right.firstVertex() if not parent.EdgesInverted else right.lastVertex())
                elif isCommonPoint(parent.Path_R[END], point):
                    if distToRight < distToLeft:
                        vertex = right if isinstance(right, Part.Vertex) else right.lastVertex() 
                        oppositeVertex = left if isinstance(left, Part.Vertex) else (left.lastVertex() if not parent.EdgesInverted else left.firstVertex())
                    else:
                        vertex = left if isinstance(left, Part.Vertex) else left.lastVertex()
                        oppositeVertex = right if isinstance(right, Part.Vertex) else (right.lastVertex() if not parent.EdgesInverted else right.firstVertex())
            else:
                App.Console.PrintError("ERROR:\n Not supported parent object type. Only Path, Move and Projection supported.\n")
        else:
            if isMovement(parent):
                (distToLeft, _, _) = vertex.distToShape(wp[0].Shape)
                (distToRight, _, _) = vertex.distToShape(wp[1].Shape)

                isLeft = distToLeft < distToRight

                if isCommonPoint(left if isinstance(left, Part.Vertex) else left.firstVertex(), vertex):                    
                    oppositeVertex = right if isinstance(right, Part.Vertex) else right.firstVertex()
                elif isCommonPoint(left if isinstance(left, Part.Vertex) else left.lastVertex(), vertex):
                    oppositeVertex = right if isinstance(right, Part.Vertex) else right.lastVertex()
                elif isCommonPoint(right if isinstance(right, Part.Vertex) else right.firstVertex(), vertex):
                    oppositeVertex =left if isinstance(left, Part.Vertex) else left.firstVertex()
                elif isCommonPoint(right if isinstance(right, Part.Vertex) else right.lastVertex(), vertex):
                    oppositeVertex = left if isinstance(left, Part.Vertex) else left.lastVertex()
            else:
                for object in job.Group:
                    if isMovement(object):
                        (left, right) = self.getEdges(object)

                        if isCommonPoint(left if isinstance(left, Part.Vertex) else left.firstVertex(), vertex):
                            isLeft = True
                            oppositeVertex = right if isinstance(right, Part.Vertex) else right.firstVertex()
                        elif isCommonPoint(left if isinstance(left, Part.Vertex) else left.lastVertex(), vertex):
                            isLeft = True
                            oppositeVertex = right if isinstance(right, Part.Vertex) else right.lastVertex()
                        elif isCommonPoint(right if isinstance(right, Part.Vertex) else right.firstVertex(), vertex):
                            oppositeVertex = left if isinstance(left, Part.Vertex) else left.firstVertex()
                        elif isCommonPoint(right if isinstance(right, Part.Vertex) else right.lastVertex(), vertex):
                            oppositeVertex = left if isinstance(left, Part.Vertex) else left.lastVertex()

        return (isLeft, vertex, oppositeVertex, wp)

    def createShape(self, obj, edges, planes, lineColor):
        # - Make path between objects on working planes
        discretizationStep = obj.DiscretizationStep if obj.DiscretizationStep > 0 else 0.5
        if len(edges) == 2:
            isLine = isStraitLine(edges[0]) and isStraitLine(edges[1])
            (path_points, inverted, points_count) = makePathPointsByEdgesPair(edges[0], edges[1], planes, discretizationStep, isLine)
        elif len(edges) == 1:
            (path_points, inverted, points_count) = makePathPointsByEdge(edges[0], planes, discretizationStep, isStraitLine(edges[0]))
        else:
            App.Console.PrintError("ERROR:\n Not supported number of edges.\n")

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
                obj.LeftEdgeLength = edges[0].Length
                obj.RightEdgeLength = obj.LeftEdgeLength
            else:
                obj.LeftEdgeLength = edges[0].Length
                obj.RightEdgeLength = edges[1].Length

            shapes = [path_L.toShape(), path_R.toShape()]

        self.validateWireStretch(obj)
        
        for edge in edges:
            shapes.append(edge)
        
        obj.Shape = Part.makeCompound(shapes)
        obj.ViewObject.LineColor = lineColor

        if hasattr(obj, "LeftEdgeName"):
            obj.LeftEdgeName = "Edge%d" % (shapes.index(edges[0]) + 1)
        if hasattr(obj, "RightEdgeName") and len(edges) > 1:
            obj.RightEdgeName = "Edge%d" % (shapes.index(edges[1]) + 1)

    def validateWireStretch(self, obj):
        config = self.getConfig(obj)

        if not config.WireStretchVerification or not float(config.WireStretchLength) > 0.0:
            return True

        if len(obj.Path_L) != len(obj.Path_R):
            App.Console.PrintError("ERROR:\n Number of point doesn't match.\n Object - {}".format(obj.Label))
            return False
        
        delta = float(config.WireStretchLength)
        wireLength = float(config.FieldWidth)

        for i in range(len(obj.Path_L)):
            stretch = obj.Path_L[i].distanceToPoint(obj.Path_R[i]) - wireLength

            if stretch > delta:
                App.Console.PrintWarning("Warning:\n Wire about to break cutting {}. Wire stretch is {:.2f}mm that is greater than allowed {:.2f}mm \n".format(obj.Label, stretch, delta))
                return False

        return True
