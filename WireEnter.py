# -*- coding: utf-8 -*-

__title__ = "Create Enter path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Enter path to selected point."
__usage__ = """Select point on left or right working plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutViewProviders
import FoamCutBase
import utilities
from utilities import getWorkingPlanes, vertexToVector, getAllSelectedObjects


class WireEnter(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, entry, config):       
        super().__init__(obj, config)      
        obj.addProperty("App::PropertyDistance",  "SafeHeight", "Task", "Safe height" )        
        obj.Type = "Enter"

        obj.addProperty("App::PropertyString",    "LeftEdgeName", "Task", "")
        obj.addProperty("App::PropertyString",    "RightEdgeName", "Task", "")
        obj.addProperty("App::PropertyLinkSub",     "EntryPoint",           "Task",   "Entry Point").EntryPoint = entry
        obj.setExpression(".SafeHeight", u"<<{}>>.SafeHeight".format(config))
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):        
        (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj.EntryPoint[0], obj.EntryPoint[0].getSubObject(obj.EntryPoint[1][0]))

        if oppositeVertex is None:
            App.Console.PrintError("ERROR:\n Unable to locate opposite vertex.\n")

        leftEdge = Part.makeLine(App.Vector(vertex.X, vertex.Y, obj.SafeHeight), vertexToVector(vertex)) if isLeft else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y, obj.SafeHeight), vertexToVector(oppositeVertex))
        rightEdge = Part.makeLine(App.Vector(vertex.X, vertex.Y, obj.SafeHeight), vertexToVector(vertex)) if not isLeft else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y, obj.SafeHeight), vertexToVector(oppositeVertex))
        
        self.createShape(obj, [leftEdge, rightEdge], wp, (0, 255, 0))

        


class WireEnterVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    def getIcon(self):
        return utilities.getIconPath("enter.svg")
    
    def claimChildren(self):
        return [self.Object.EntryPoint[0]] if self.Object.EntryPoint is not None and len(self.Object.EntryPoint) > 0 else None


class MakeEnter():
    """Make Enter"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("enter.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create enter",
                "ToolTip" : "Create enter path object to selected entry point"}

    def Activated(self):     
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":    
            # - Get selecttion
            objects = getAllSelectedObjects()
            
            # - Create object
            enter = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Enter")
            WireEnter(enter, objects[0], group.ConfigName)
            WireEnterVP(enter.ViewObject)
            enter.ViewObject.PointSize = 4
    
            group.addObject(enter)
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
            
Gui.addCommand("MakeEnter", MakeEnter())
