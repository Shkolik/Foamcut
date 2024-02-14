# -*- coding: utf-8 -*-

__title__ = "Base classes"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
from utilities import getWorkingPlanes, vertexToVector, isCommonPoint, makePathPointsByEdgesPair, START, END

class FoamCutBaseObject:
    def __init__(self, obj):
        obj.addProperty("App::PropertyString",    "Type", "", "", 5)
        obj.setEditorMode("Placement", 3)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

class FoamCutMovementBaseObject(FoamCutBaseObject):
    def __init__(self, obj, config):
        super().__init__(obj)  
        obj.addProperty("App::PropertyVectorList",  "Path_L",     "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Path_R",     "", "", 5)

        obj.addProperty("App::PropertyString",    "LeftEdgeName", "", "", 5)
        obj.addProperty("App::PropertyString",    "RightEdgeName", "", "", 5)

        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",    "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",   "Information", "Right Segment length",   1)
        obj.addProperty("App::PropertyLength",      "DiscretizationStep",   "Information", "Discretization step")
        obj.addProperty("App::PropertyInteger",     "PointsCount",          "Information", "Number of points", 1)

        
        obj.addProperty("App::PropertyBool",        "AddPause",             "Task", "Add pause at the end of move").AddPause = False
        obj.addProperty("App::PropertyTime",        "PauseDuration",        "Task", "Pause duration seconds")
        obj.addProperty("App::PropertyBool",        "ShowProjectionLines",  "Task", "Show projection lines between planes").ShowProjectionLines = False
        
        obj.setExpression(".DiscretizationStep", u"<<{}>>.DiscretizationStep".format(config))
        obj.setExpression(".PauseDuration", u"<<{}>>.PauseDuration".format(config))

        obj.setEditorMode("PauseDuration", 3)

    def onChanged(self, obj, prop):
        if prop == "AddPause":
            if obj.AddPause:
                obj.setEditorMode("PauseDuration", 0)
            else:
                obj.setEditorMode("PauseDuration", 3)
        # App.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def findOppositeVertexes(self, parent, vertex):
        oppositeVertex = None

        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is None or group.Type != "Job":
            App.Console.PrintError("ERROR:\n Error updating Enter - active Job not found\n")

        wp = getWorkingPlanes(group)

        onPlane = wp[0].Shape.isInside(vertexToVector(vertex), 0.01, True) or wp[1].Shape.isInside(vertexToVector(vertex), 0.01, True)

        isLeft = False

        left = parent.LeftEdge[0].getSubObject(parent.LeftEdge[1][0]) if hasattr(parent, "LeftEdge") else parent.getSubObject(parent.LeftEdgeName)
        right = parent.RightEdge[0].getSubObject(parent.RightEdge[1][0]) if hasattr(parent, "RightEdge") else parent.getSubObject(parent.RightEdgeName)

        if onPlane:
            if hasattr(parent, "Type") and (parent.Type == "Path" or parent.Type == "Move"):
                point = vertexToVector(vertex)
                # - Connect
                if isCommonPoint(parent.Path_L[START], point):
                    isLeft = True
                    vertex = left.firstVertex()
                    oppositeVertex = right.firstVertex()
                elif isCommonPoint(parent.Path_R[START], point):                
                    vertex = right.firstVertex()
                    oppositeVertex = left.firstVertex()
                elif isCommonPoint(parent.Path_L[END], point):
                    isLeft = True
                    vertex = left.lastVertex()
                    oppositeVertex = right.lastVertex()
                elif isCommonPoint(parent.Path_R[END], point):
                    vertex = right.lastVertex()
                    oppositeVertex = left.lastVertex()
            else:
                App.Console.PrintError("ERROR:\n Not supported parent object type. Only Path, Move and Projection supported.\n")
        else:
            if hasattr(parent, "Type") and (parent.Type == "Path" or parent.Type == "Move"):    
                if isCommonPoint(left.firstVertex(), vertex):
                    isLeft = True
                    oppositeVertex = right.firstVertex()
                elif isCommonPoint(left.lastVertex(), vertex):
                    isLeft = True
                    oppositeVertex = right.lastVertex()
                elif isCommonPoint(right.firstVertex(), vertex):
                    oppositeVertex = left.firstVertex()
                elif isCommonPoint(right.lastVertex(), vertex):
                    oppositeVertex = left.lastVertex()
            else:
                for object in group.Group:
                    if hasattr(object, "Type") and (object.Type == "Path" or object.Type == "Move"):
                        left = parent.getSubObject(object.LeftEdge[1][0])
                        right = parent.getSubObject(object.RightEdge[1][0])
                        
                        if object.LeftEdge[0] == parent:
                            if isCommonPoint(left.firstVertex(), vertex):
                                isLeft = True
                                oppositeVertex = object.RightEdge[0].getSubObject(object.RightEdge[1][0]).firstVertex()
                                break
                            elif isCommonPoint(left.lastVertex(), vertex):
                                isLeft = True
                                oppositeVertex = object.RightEdge[0].getSubObject(object.RightEdge[1][0]).lastVertex()
                                break

                        if object.RightEdge[0] == parent:
                            if isCommonPoint(right.firstVertex(), vertex):
                                oppositeVertex = object.LeftEdge[0].getSubObject(object.LeftEdge[1][0]).firstVertex()
                                break
                            elif isCommonPoint(right.lastVertex(), vertex):
                                oppositeVertex = object.LeftEdge[0].getSubObject(object.LeftEdge[1][0]).lastVertex()
                                break
        return (isLeft, vertex, oppositeVertex, wp)

    def createShape(self, obj, edges, planes, lineColor):
        # - Make path between objects on working planes
        path_points = makePathPointsByEdgesPair(edges[0], edges[1], planes, obj.DiscretizationStep if obj.DiscretizationStep > 0 else 0.5)

        # - Set data
        obj.Path_L       = [item for item in path_points[START]]
        obj.Path_R       = [item for item in path_points[END]]        
        obj.PointsCount = int(len(path_points[START]))
        #

        # - Create path for L
        path_L = Part.BSplineCurve()
        path_L.approximate(Points = obj.Path_L, Continuity="C0")

        # - Create path for R
        path_R = Part.BSplineCurve()
        path_R.approximate(Points = obj.Path_R, Continuity="C0")

        shapes = [path_L.toShape(), path_R.toShape(), edges[0], edges[1]]
        
        if obj.ShowProjectionLines:
            shapes.append(Part.makeLine(obj.Path_L[START] , obj.Path_R[START]))
            shapes.append(Part.makeLine(obj.Path_L[END] , obj.Path_R[END] ))

        obj.LeftSegmentLength = float(path_L.length())
        obj.RightSegmentLength = float(path_R.length())
        obj.Shape = Part.makeCompound(shapes)
        obj.ViewObject.LineColor = lineColor

        if hasattr(obj, "LeftEdgeName") and hasattr(obj, "RightEdgeName"):
            obj.LeftEdgeName = "Edge%d" % (shapes.index(edges[0]) + 1)
            obj.RightEdgeName = "Edge%d" % (shapes.index(edges[1]) + 1)
