# -*- coding: utf-8 -*-

__title__ = "Create Exit path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Exit path from selected point."
__usage__ = """Select start point on left or right working plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import utilities
from utilities import getWorkingPlanes, vertexToVector, isCommonPoint, makePathPointsByEdgesPair
from utilities import getAllSelectedObjects, START, END

class WireExit:
    def __init__(self, obj, exit, config):
        obj.addProperty("App::PropertyDistance",  "SafeHeight", "Task", "Safe height")
        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Exit"
        
        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",    "Information", "Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",   "Information", "Segment length",   1)
        obj.addProperty("App::PropertyLength",      "DiscretizationStep",   "Information", "Discretization step") 
        obj.addProperty("App::PropertyInteger",     "PointsCount",          "Information", "Number of points", 1)

        obj.addProperty("App::PropertyVectorList",  "Path_L",     "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Path_R",     "", "", 5)

        obj.addProperty("App::PropertyLinkSub",     "ExitPoint",            "Task",     "Exit Point").ExitPoint = exit
        obj.addProperty("App::PropertyBool",        "AddPause",             "Task",     "Add pause at the end of move").AddPause = False
        obj.addProperty("App::PropertyTime",        "PauseDuration",        "Task",     "Pause duration seconds")

        obj.setExpression(".SafeHeight", u"<<{}>>.SafeHeight".format(config))
        obj.setExpression(".DiscretizationStep", u"<<{}>>.DiscretizationStep".format(config))
        obj.setExpression(".PauseDuration", u"<<{}>>.PauseDuration".format(config))

        obj.setEditorMode("PauseDuration", 3)
        obj.setEditorMode("Placement", 3)
        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, obj, prop):
        if prop == "AddPause":
            if obj.AddPause:
                obj.setEditorMode("PauseDuration", 0)
            else:
                obj.setEditorMode("PauseDuration", 3)
        # App.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(this, obj): 
        parent = obj.ExitPoint[0]
        vertex = parent.getSubObject(obj.ExitPoint[1][0])
        oppositeVertex = None

        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is None or group.Type != "Job":
            App.Console.PrintError("ERROR:\n Error updating Exit - active Job not found\n")

        wp = getWorkingPlanes(group)

        onPlane = wp[0].Shape.isInside(vertexToVector(vertex), 0.01, True) or wp[1].Shape.isInside(vertexToVector(vertex), 0.01, True)

        isLeft = False
        
        if onPlane:
            if hasattr(parent, "Type") and (parent.Type == "Path" or parent.Type == "Move" or parent.Type == "Projection"):
                point = vertexToVector(vertex)
                # - Connect
                if isCommonPoint(parent.Path_L[START], point):
                    vertex = parent.LeftEdge[0].getSubObject(parent.LeftEdge[1][0]).firstVertex()
                    oppositeVertex = parent.RightEdge[0].getSubObject(parent.RightEdge[1][0]).firstVertex()
                elif isCommonPoint(parent.Path_R[START], point):                
                    vertex = parent.RightEdge[0].getSubObject(parent.RightEdge[1][0]).firstVertex()
                    oppositeVertex = parent.LeftEdge[0].getSubObject(parent.LeftEdge[1][0]).firstVertex()

                elif isCommonPoint(parent.Path_L[END], point):
                    vertex = parent.LeftEdge[0].getSubObject(parent.LeftEdge[1][0]).lastVertex()
                    oppositeVertex = parent.RightEdge[0].getSubObject(parent.RightEdge[1][0]).lastVertex()
                elif isCommonPoint(parent.Path_R[END], point):
                    vertex = parent.RightEdge[0].getSubObject(parent.RightEdge[1][0]).lastVertex()
                    oppositeVertex = parent.LeftEdge[0].getSubObject(parent.LeftEdge[1][0]).lastVertex()
            else:
                App.Console.PrintError("ERROR:\n Not supported parent object type. Only Path, Move and Projection supported.\n")
        else:
            if hasattr(parent, "Type") and (parent.Type == "Path" or parent.Type == "Move" or parent.Type == "Projection"):                
                left = parent.LeftEdge[0].getSubObject(parent.LeftEdge[1])[0]
                right = parent.RightEdge[0].getSubObject(parent.RightEdge[1])[0]

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
                    if hasattr(object, "Type") and (object.Type == "Path" or object.Type == "Move" or object.Type == "Projection"):
                        if object.LeftEdge[0] == parent:
                            left = parent.getSubObject(object.LeftEdge[1][0])
                            if isCommonPoint(left.firstVertex(), vertex):
                                isLeft = True
                                oppositeVertex = object.RightEdge[0].getSubObject(object.RightEdge[1][0]).firstVertex()
                                break
                            elif isCommonPoint(left.lastVertex(), vertex):
                                isLeft = True
                                oppositeVertex = object.RightEdge[0].getSubObject(object.RightEdge[1][0]).lastVertex()
                                break

                        if object.RightEdge[0] == parent:
                            right = parent.getSubObject(object.RightEdge[1][0])
                            if isCommonPoint(right.firstVertex(), vertex):
                                oppositeVertex = object.LeftEdge[0].getSubObject(object.LeftEdge[1][0]).firstVertex()
                                break
                            elif isCommonPoint(right.lastVertex(), vertex):
                                oppositeVertex = object.LeftEdge[0].getSubObject(object.LeftEdge[1][0]).lastVertex()
                                break
            if oppositeVertex is None:
                App.Console.PrintError("ERROR:\n Unable to locate opposite vertex.\n")

        leftEdge = Part.makeLine(App.Vector(vertex.X, vertex.Y, obj.SafeHeight), vertexToVector(vertex)) if isLeft else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y, obj.SafeHeight), vertexToVector(oppositeVertex))
        rightEdge = Part.makeLine(App.Vector(vertex.X, vertex.Y, obj.SafeHeight), vertexToVector(vertex)) if not isLeft else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y, obj.SafeHeight), vertexToVector(oppositeVertex))
        
        # - Make path between objects on working planes
        path_points = makePathPointsByEdgesPair(leftEdge, rightEdge, wp, 0.5)

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

        shapes = [path_L.toShape(), path_R.toShape(), leftEdge, rightEdge]
        
        obj.LeftSegmentLength = float(path_L.length())
        obj.RightSegmentLength = float(path_R.length())
        obj.Shape = Part.makeCompound(shapes)
        obj.ViewObject.LineColor = (1.0, 0.0, 0.0)
        
class WireExitVP:
    def __init__(this, obj):
        obj.Proxy = this

    def attach(this, obj):
        this.Object = obj.Object

    def getIcon(self):        
        return utilities.getIconPath("exit.svg")

    if utilities.isNewStateHandling(): # - currently supported only in main branch FreeCad v0.21.2 and up
        def dumps(self):
            return {"name": self.Object.Name}

        def loads(self, state):
            self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
            return None
    else:
        def __getstate__(self):
            return {"name": self.Object.Name}

        def __setstate__(self, state):
            self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
            return None
    
    def claimChildren(self):
        return [self.Object.ExitPoint[0]] if self.Object.ExitPoint is not None and len(self.Object.ExitPoint) > 0 else None

    def doubleClicked(self, obj):
        return True

class MakeExit():
    """Make Exit"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("exit.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create exit",
                "ToolTip" : "Create exit path object from selected entry point"}

    def Activated(self):
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":     
            # - Get selecttion
            objects = utilities.getAllSelectedObjects()
            
            # - Create object
            exit = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Exit")
            WireExit(exit, objects[0], group.ConfigName)
            WireExitVP(exit.ViewObject)
            exit.ViewObject.PointSize = 4
            
            group.addObject(exit)

            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            if group is not None and group.Type == "Job":
                # - Get selecttion
                objects = getAllSelectedObjects()

                # - nothing selected
                if len(objects) == 0:
                    return False
                
                object = objects[0]
                parent = object[0]
                vertex = parent.getSubObject(object[1][0])
                # - Check object type
                if not issubclass(type(vertex), Part.Vertex):
                    return False
                
                wp = getWorkingPlanes(group)
                if wp is None or len(wp) != 2:
                    return False
                
                return True
            return False
        
Gui.addCommand("MakeExit", MakeExit())
