# -*- coding: utf-8 -*-

__title__ = "Join 2 points with path"
__author__ = "Andrew Shkolik & Andrei Bezborodov LGPL"
__license__ = "LGPL 2.1"
__doc__ = "Join 2 selected points with path."
__usage__ = """Select two points on left or right plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutViewProviders
import FoamCutBase
import utilities
from utilities import vertexToVector, getAllSelectedObjects, isCommonPoint, isMovement

class WireJoin(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, start, end, jobName):  
        super().__init__(obj, jobName)  
        obj.Type = "Join"
        obj.addProperty("App::PropertyLength",    "FieldWidth","","",5)

        # - Options
        obj.addProperty("App::PropertySpeed",     "FeedRate",  "Options",  "Feed rate" )
        obj.addProperty("App::PropertyInteger",   "WirePower", "Options",  "Wire power")

        obj.addProperty("App::PropertyLinkSub",      "StartPoint",      "Task",   "Start Point").StartPoint = start
        obj.addProperty("App::PropertyLinkSub",      "EndPoint",        "Task",   "Start Point").EndPoint = end

        config = self.getConfigName(obj)
        obj.setExpression(".FeedRate", u"<<{}>>.FeedRateCut".format(config))
        obj.setExpression(".WirePower", u"<<{}>>.WireMinPower".format(config))
        obj.setExpression(".FieldWidth", u"<<{}>>.FieldWidth".format(config))
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
        
        (isLeftA, vertexA, oppositeVertexA, wp) = self.findOppositeVertexes(obj, obj.StartPoint[0], obj.StartPoint[0].getSubObject(obj.StartPoint[1][0]))
        (isLeftB, vertexB, oppositeVertexB, wp) = self.findOppositeVertexes(obj, obj.EndPoint[0], obj.EndPoint[0].getSubObject(obj.EndPoint[1][0]))

        if oppositeVertexA is None:
            App.Console.PrintError("ERROR:\n Unable to locate opposite vertex for the start point.\n")

        if oppositeVertexB is None:
            App.Console.PrintError("ERROR:\n Unable to locate opposite vertex for the end point.\n")

        if isLeftA != isLeftB:
            App.Console.PrintError("ERROR:\n Start and End points should be on one side.\n")

        edges = []

        if isCommonPoint(vertexA, oppositeVertexA):
            edges.append(Part.makeLine(vertexToVector(vertexA), vertexToVector(vertexB)))
        else:
            edges.append(Part.makeLine(vertexToVector(vertexA), vertexToVector(vertexB)))
            edges.append(Part.makeLine(vertexToVector(oppositeVertexA), vertexToVector(oppositeVertexB)))
        
        self.createShape(obj, edges, wp, (35, 0, 205))

class WireJoinVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    def getIcon(self):
        return utilities.getIconPath("join.svg")

    def claimChildren(self):
        if (self.Object.StartPoint is not None and len(self.Object.StartPoint) > 0 
            and self.Object.EndPoint is not None and len(self.Object.EndPoint) > 0 ):
            return [self.Object.StartPoint[0], self.Object.EndPoint[0]]
        return None


class MakeJoin():
    """Make Join"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("join.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Join 2 points",
                "ToolTip" : "Join 2 selected coplanar points"}

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
            objects = getAllSelectedObjects()
            
            # - Create object
            join = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Join")
            WireJoin(join, objects[0], objects[1], group.Name)
            WireJoinVP(join.ViewObject)
            join.ViewObject.PointSize = 4
    
            group.addObject(join)
            Gui.Selection.clearSelection()
            FreeCAD.ActiveDocument.recompute()
    
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
                if len(objects) < 2:
                    return False
                
                parentA = objects[0][0]
                parentB = objects[1][0]
                # - Check object type
                if isMovement(parentA) or isMovement(parentB):   
                    return True
                
            return False
            
Gui.addCommand("Join", MakeJoin())
