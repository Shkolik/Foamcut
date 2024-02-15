# -*- coding: utf-8 -*-

__title__ = "Make Path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Make Path from 2 selected opposite edges."
__usage__ = """Select 2 opposite edges and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutViewProviders
import FoamCutBase
import utilities
from utilities import getWorkingPlanes, getAllSelectedObjects

class PathSection(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, edge_l, edge_r, jobName):
        super().__init__(obj, jobName)      
        obj.Type = "Path"

        obj.addProperty("App::PropertyLinkSub",     "LeftEdge",             "Edges",    "Left Edge").LeftEdge = edge_l
        obj.addProperty("App::PropertyLinkSub",     "RightEdge",            "Edges",    "Right Edge").RightEdge = edge_r
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):  
        job = App.ActiveDocument.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            App.Console.PrintError("ERROR:\n Error updating Enter - active Job not found\n")

        wp = getWorkingPlanes(job)
      
        leftEdge = obj.LeftEdge[0].getSubObject(obj.LeftEdge[1])[0]
        rightEdge = obj.RightEdge[0].getSubObject(obj.RightEdge[1])[0]
        
        self.createShape(obj, [leftEdge, rightEdge], wp, (0, 0, 0))

class PathSectionVP(FoamCutViewProviders.FoamCutBaseViewProvider): 
    def getIcon(self):
        return utilities.getIconPath("path.svg")

    def claimChildren(self):
        if (self.Object.LeftEdge is not None and len(self.Object.LeftEdge) > 0 
            and self.Object.RightEdge is not None and len(self.Object.RightEdge) > 0 ):
            return [self.Object.LeftEdge[0], self.Object.RightEdge[0]] if self.Object.LeftEdge[0] != self.Object.RightEdge[0] else [self.Object.LeftEdge[0]]
        return None

class MakePath():
    """Make Path"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("path.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create path",
                "ToolTip" : "Create path object from 2 selected opposite edges"}

    def Activated(self):
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":
            # - Get selected objects
            objects = utilities.getAllSelectedObjects()
            obj = group.newObject("Part::FeaturePython","Path")
            
            PathSection(obj, 
                        (FreeCAD.ActiveDocument.getObject((objects[0])[0].Name), (objects[0])[1][0]), 
                        (FreeCAD.ActiveDocument.getObject((objects[1])[0].Name),(objects[1])[1][0]),
                        group.Name)
            PathSectionVP(obj.ViewObject)
            obj.ViewObject.PointSize = 4

            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()
    
    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            if group is not None and group.Type == "Job":  
                # - Get selected objects
                objects = getAllSelectedObjects()

                # - Number of edges should be two
                if len(objects) != 2:               
                    return False
                
                wp = getWorkingPlanes(group)
                if wp is None or len(wp) != 2:
                    return False                    
                return True
            return False
            
Gui.addCommand("MakePath", MakePath())
