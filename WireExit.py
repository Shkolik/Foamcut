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
import FoamCutViewProviders
import FoamCutBase
import utilities
from utilities import getWorkingPlanes, vertexToVector, getAllSelectedObjects

class WireExit(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, exit, config):
        super().__init__(obj, config) 
        
        obj.Type = "Exit"
        
        obj.addProperty("App::PropertyDistance",    "SafeHeight",           "Task",     "Safe height")
        obj.addProperty("App::PropertyLinkSub",     "ExitPoint",            "Task",     "Exit Point").ExitPoint = exit

        obj.setExpression(".SafeHeight", u"<<{}>>.SafeHeight".format(config))
        obj.Proxy = self

        self.execute(obj)

    def execute(self, obj): 
        (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj.ExitPoint[0], obj.ExitPoint[0].getSubObject(obj.ExitPoint[1][0]))

        if oppositeVertex is None:
            App.Console.PrintError("ERROR:\n Unable to locate opposite vertex.\n")
            
        leftEdge = Part.makeLine(App.Vector(vertex.X, vertex.Y, obj.SafeHeight), vertexToVector(vertex)) if isLeft else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y, obj.SafeHeight), vertexToVector(oppositeVertex))
        rightEdge = Part.makeLine(App.Vector(vertex.X, vertex.Y, obj.SafeHeight), vertexToVector(vertex)) if not isLeft else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y, obj.SafeHeight), vertexToVector(oppositeVertex))
        
        self.createShape(obj, [leftEdge, rightEdge], wp, (255, 0, 0))
        
class WireExitVP(FoamCutViewProviders.FoamCutBaseViewProvider):    
    def getIcon(self):        
        return utilities.getIconPath("exit.svg")

    def claimChildren(self):
        return [self.Object.ExitPoint[0]] if self.Object.ExitPoint is not None and len(self.Object.ExitPoint) > 0 else None

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
