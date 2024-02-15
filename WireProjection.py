# -*- coding: utf-8 -*-

__title__ = "Make Path"
__author__ = "Andrew Shkolik"
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


class ProjectionSection(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, source, jobName):
        super().__init__(obj, jobName)
        obj.Type = "Projection"
        obj.addProperty("App::PropertyLinkSub",     "Source",               "Data",         "Source object to project").Source = source
                
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
       
        job = App.ActiveDocument.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            FreeCAD.Console.PrintError("ERROR:\n Error updating Projection - active Job not found\n")

        # - Get working planes
        wp = getWorkingPlanes(job)
        
        if wp is None or len(wp) != 2:
            FreeCAD.Console.PrintError("ERROR:\n Error updating Path - working planes not found in Parent object '{}'\n".format(job.Label if job is not None else "None"))

        source = obj.Source[0].getSubObject(obj.Source[1])[0]

        self.createShape(obj, [source], wp, (0, 0, 0))
                

class ProjectionSectionVP(FoamCutViewProviders.FoamCutBaseViewProvider):     
    def getIcon(self):
        return utilities.getIconPath("projection.svg")

    def claimChildren(self):
        if self.Object.Source is not None and len(self.Object.Source) > 0:
            return [self.Object.Source[0]]
        return None
    
class MakeProjection():
    """Make Projection"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("projection.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create Projection",
                "ToolTip" : "Create projection object from selected edge or vertex"}

    def Activated(self):
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":
            # - Get selected objects
            objects = getAllSelectedObjects()
            obj = group.newObject("Part::FeaturePython","Projection")
            
            ProjectionSection(obj, 
                        (FreeCAD.ActiveDocument.getObject((objects[0])[0].Name), (objects[0])[1][0]), 
                        group.Name)
            ProjectionSectionVP(obj.ViewObject)
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
                if len(objects) < 1:               
                    return False
                
                wp = getWorkingPlanes(group)
                if wp is None or len(wp) != 2:
                    return False                    
                return True
            return False
            
Gui.addCommand("MakeProjection", MakeProjection())
