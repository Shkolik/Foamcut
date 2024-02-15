# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Move path from selected point."
__usage__ = """Select start point on left or right plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutViewProviders
import FoamCutBase
import utilities
from utilities import getWorkingPlanes, vertexToVector, getAllSelectedObjects, isCommonPoint

class WireMove(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, start, jobName):     
        super().__init__(obj, jobName)     
        obj.Type = "Move"

        # - Options
        obj.addProperty("App::PropertyDistance",    "MoveX",        "Task",     "Move along X machine axis" ).MoveX = 100
        obj.addProperty("App::PropertyDistance",    "MoveY",        "Task",     "Move along Y machine axis" ).MoveY = 0
        obj.addProperty("App::PropertySpeed",       "FeedRate",     "Task",     "Feed rate")
        obj.addProperty("App::PropertyInteger",     "WirePower",    "Task",     "Wire power")
        obj.addProperty("App::PropertyLinkSub",     "StartPoint",   "Task",     "Start Point").StartPoint = start

        config = self.getConfigName(obj)
        obj.setExpression(".FeedRate", u"<<{}>>.FeedRateCut".format(config))
        obj.setExpression(".WirePower", u"<<{}>>.WireMinPower".format(config))

        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):        
        (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj, obj.StartPoint[0], obj.StartPoint[0].getSubObject(obj.StartPoint[1][0]))

        if oppositeVertex is None:
            App.Console.PrintError("ERROR:\n Unable to locate opposite vertex.\n")
            
        edges = []

        if isCommonPoint(vertex, oppositeVertex):
            edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertexToVector(vertex)))
        else:
            edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertexToVector(vertex)) if isLeft                      \
                else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y + float(obj.MoveX), oppositeVertex.Z + float(obj.MoveY)), vertexToVector(oppositeVertex)))
            edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertexToVector(vertex)) if not isLeft                  \
                else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y + float(obj.MoveX), oppositeVertex.Z + float(obj.MoveY)), vertexToVector(oppositeVertex)))
        
        self.createShape(obj, edges, wp, (35, 169, 205))

class WireMoveVP(FoamCutViewProviders.FoamCutBaseViewProvider):     
    def getIcon(self):
        return utilities.getIconPath("move.svg")

    def claimChildren(self):
        return [self.Object.StartPoint[0]] if self.Object.StartPoint is not None and len(self.Object.StartPoint) > 0 else None

class MakeMove():
    """Make Move"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("move.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create move path",
                "ToolTip" : "Create move path object from selected point in specified direction"}

    def Activated(self):    
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":        
            # - Get selecttion
            objects = getAllSelectedObjects()
            
            # - Create object
            move = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Move")
            WireMove(move, objects[0], group.Name)
            WireMoveVP(move.ViewObject)
            move.ViewObject.PointSize = 4

            group.addObject(move)

            move.recompute()
    
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
            
Gui.addCommand("MakeMove", MakeMove())
