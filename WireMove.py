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
from utilities import *

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
        try:

            (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj, obj.StartPoint[0], obj.StartPoint[0].getSubObject(obj.StartPoint[1][0]))
            
            if oppositeVertex is None:
                raise Exception(f"ERROR:\n Unable to locate opposite vertex.\n")
                
            edges = []

            if isCommonPoint(vertex, oppositeVertex):
                edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertex.Point))
            else:
                edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertex.Point) if isLeft                      \
                    else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y + float(obj.MoveX), oppositeVertex.Z + float(obj.MoveY)), oppositeVertex.Point))
                edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertex.Point) if not isLeft                  \
                    else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y + float(obj.MoveX), oppositeVertex.Z + float(obj.MoveY)), oppositeVertex.Point))
            
            self.createShape(obj, edges, wp, (35, 169, 205))
        except Exception as e:
            FreeCAD.Console.PrintError(f"Move {obj.Label} {e}\n")
            raise

class WireMoveVP(FoamCutViewProviders.FoamCutMovementViewProvider):     
    def getIcon(self):
        return getIconPath("move.svg")

    def claimChildren(self):
        return [self.Object.StartPoint[0]] if self.Object.StartPoint is not None and len(self.Object.StartPoint) > 0 else None

class MakeMove():
    """Make Move"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("move.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create move path",
                "ToolTip" : "Create move path object from selected point in specified direction"}

    def Activated(self):    
        doc = App.ActiveDocument
        view = Gui.ActiveDocument.ActiveView

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
            objects = getAllSelectedObjects()
            
            move = None
            try:
                # - Create object
                move = doc.addObject("Part::FeaturePython", "Move")
                WireMove(move, objects[0], group.Name)
                WireMoveVP(move.ViewObject)
                move.ViewObject.PointSize = 4

                group.addObject(move)

                Gui.Selection.clearSelection()
                doc.recompute()
                Gui.Selection.addSelection(doc.Name, move.Name)
                
            except Exception as e:                
                FreeCAD.Console.PrintError(f"Failed to create Move.\n")
                if move is not None:
                    doc.removeObject(move.Name) 
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

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
                
                wp = getWorkingPlanes(group, App.ActiveDocument)
                if wp is None or len(wp) != 2:
                    return False
                
                return True
            return False
            
Gui.addCommand("MakeMove", MakeMove())
