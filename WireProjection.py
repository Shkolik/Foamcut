# -*- coding: utf-8 -*-

__title__ = "Create Projection"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Create projection from selected face, edge or vertex."
__usage__ = """Select face, edge or vertex and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutViewProviders
import FoamCutBase
import Part
import utilities
from utilities import getWorkingPlanes, getAllSelectedObjects, getEdgesLinks


class ProjectionSection(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, source, jobName):
        super().__init__(obj, jobName)
        obj.Type = "Projection"
        obj.addProperty("App::PropertyLinkSub", "Source", "Data", "Source object to project").Source = source

        obj.setEditorMode("CompensationDirection", 3)
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
        try:
            job = obj.Document.getObject(obj.JobName)
            if job is None or job.Type != "Job":
                raise Exception(f"ERROR: Active Job not found\n")

            # - Get working planes
            wp = getWorkingPlanes(job, obj.Document)
            
            if wp is None or len(wp) != 2:
                label = job.Label if job is not None else "None"
                raise Exception(f"ERROR: Working planes not found in Parent object '{label}'\n")

            source = obj.Source[0].getSubObject(obj.Source[1])[0]

            self.createShape(obj, [source], wp, (0, 0, 0))
        except Exception as e:
            FreeCAD.Console.PrintError(f"Projection {obj.Label} {e}\n")
            raise   

class ProjectionSectionVP(FoamCutViewProviders.FoamCutMovementViewProvider):     
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
                "ToolTip" : "Create projection object from selected face, edge or vertex. Separate projection will be created for each edge or vertex."}

    def CreateFromEdge(self, edge, group):
        projection = None
        try:
            projection = group.newObject("Part::FeaturePython","Projection")
                
            ProjectionSection(projection, (edge[0], (edge)[1][0]), group.Name)
            ProjectionSectionVP(projection.ViewObject)
            projection.ViewObject.PointSize = 4
        except Exception as e:
            FreeCAD.Console.PrintError(f"Failed to create projection from edge {edge[0].Name}\n")
            if projection is not None:
                projection.Document.removeObject(projection.Name)    

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
            
            # - Get selected objects
            objects = getAllSelectedObjects(True)

            baseObjects = []

            for object in objects:
                if object[1][0].startswith("Face"):
                    # - prepare base object. 
                    # - Sometimes, after reopening file it is necessary to recompute em or list of edges will be empty
                    if object[0].Name not in baseObjects:
                        object[0].touch()
                        baseObjects.append(object[0].Name)
                        object[0].recompute(True)

                    edges = getEdgesLinks(object[0], object[0].getSubObject(object[1][0]))

                    if len(edges) == 0:
                        FreeCAD.Console.PrintError("ERROR: No edges of the selected face [{}] match the object shape. Select edges directly instead.\n".format(object[0].Label))
                        return

                    for edge in edges:
                        self.CreateFromEdge(edge, group)
                else:
                    self.CreateFromEdge(object, group)

            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()
    
    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":  
                # - Get selected objects including Faces
                objects = getAllSelectedObjects(True)

                # - at least one Edge, Vertex or Face should be selected
                if len(objects) == 0:               
                    return False
                
                wp = getWorkingPlanes(group, App.ActiveDocument)
                if wp is None or len(wp) != 2:
                    return False                    
                return True
            return False
            
Gui.addCommand("MakeProjection", MakeProjection())
