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
import Part
import utilities
from utilities import makePathByPointSets, START, END


'''
  Make projected path on working planes by one edge or vertex
  @param first - First edge / vertex
  @param planes - working planes 
  @param step - Distance between points in edge discretization
'''
def makePathPointsByEdge(first, planes, step = 0.1):
    # # --- Use only end vertices of coplanar edges or lines because path will be a straight line
    # if first.ShapeType == "Edge" and first.Curve.TypeId == "Part::GeomLine":
        
    #     # - Make path
    #     return makePathByPointSets([utilities.vertexToVector(first.firstVertex()), utilities.vertexToVector(first.lastVertex())], None, planes)

    # # --- This not coplanar edges
    # else:
    #     # - Detect vertex and vertex
    #     if first.ShapeType == "Vertex":
    #         return makePathByPointSets([first.Point], None, planes, True)

    #     # - Calculate number of discretization points
    #     points_count = int(float(first.Length) / float(step))
           
    #     print("Point count = %d" % points_count)

    #     first_set   = []

    #     # - Discretize first edge
    #     first_set = first.discretize(Number=points_count) if points_count > 2 else [first.firstVertex().Point, first.lastVertex().Point]

    #     # - Make path
    #     return makePathByPointSets(first_set, None,  planes, True)
    
    # - Detect vertex and vertex
    if first.ShapeType == "Vertex":
        return makePathByPointSets([first.Point], None, planes, True)

    # - Calculate number of discretization points
    points_count = int(float(first.Length) / float(step))
        
    print("Point count = %d" % points_count)

    first_set   = []

    # - Discretize first edge
    first_set = first.discretize(Number=points_count) if points_count > 2 else [first.firstVertex().Point, first.lastVertex().Point]

    # - Make path
    return makePathByPointSets(first_set, None,  planes, True)

class ProjectionSection:
    def __init__(self, obj, source, config):
        obj.addProperty("App::PropertyVectorList",  "Path_L",     "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Path_R",     "", "", 5)
        obj.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Projection"

        obj.addProperty("App::PropertyLinkSub",     "Source",               "Data",         "Source object to project").Source = source
        
        obj.addProperty("App::PropertyLength",      "DiscretizationStep",   "Information",  "Discretization step") 
        obj.addProperty("App::PropertyInteger",     "PointsCount",          "Information",  "Number of points", 1)
        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",    "Information",  "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",   "Information",  "Right Segment length",   1)
        obj.addProperty("App::PropertyBool",        "ShowProjectionLines",  "Information",  "Show projection lines between planes").ShowProjectionLines = False

        obj.addProperty("App::PropertyBool",        "AddPause",             "Task",   "Add pause at the end of move").AddPause = False
        obj.addProperty("App::PropertyTime",        "PauseDuration",        "Task", "Pause duration seconds")

        obj.setExpression(".DiscretizationStep", u"<<{}>>.DiscretizationStep".format(config))
        obj.setExpression(".PauseDuration", u"<<{}>>.PauseDuration".format(config))

        obj.setEditorMode("Placement", 3)
        obj.setEditorMode("PauseDuration", 3)
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

    def execute(self, obj):
       
        job = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if job is None or job.Type != "Job":
            FreeCAD.Console.PrintError("ERROR:\n Error updating Projection - active Job not found\n")

        # - Get working planes
        wp = utilities.getWorkingPlanes(job)
        
        if wp is None or len(wp) != 2:
            FreeCAD.Console.PrintError("ERROR:\n Error updating Path - working planes not found in Parent object '{}'\n".format(job.Label if job is not None else "None"))

        source = obj.Source[0].getSubObject(obj.Source[1])[0]
        
        # - Make path between objects on working planes
        path_points = makePathPointsByEdge(source, wp, obj.DiscretizationStep if obj.DiscretizationStep > 0 else 0.5)

        # - Set data
        obj.Path_L       = [item for item in path_points[START]]
        obj.Path_R       = [item for item in path_points[END]]        
        obj.PointsCount  = int(len(path_points[START]))
        #

        shapes = []
        l_points = obj.Path_L
        r_points = obj.Path_R
        
        if obj.PointsCount == 1:
            shapes = [Part.Point(obj.Path_L[START]), Part.Point(obj.Path_R[START]), source]
            obj.LeftSegmentLength = 0.0
            obj.RightSegmentLength = 0.0      
        else:
            sameY = True
            tempY = obj.Path_L[START].y
            for point in obj.Path_L:
                if tempY != point.y:
                    sameY = False
                    break

            if sameY:
                minZ = min(obj.Path_L, key=lambda point: point.z)
                maxZ = max(obj.Path_L, key=lambda point: point.z)
                
                l_points = [minZ, maxZ]
                
                minZ = min(obj.Path_R, key=lambda point: point.z)
                maxZ = max(obj.Path_R, key=lambda point: point.z)
                
                r_points = [minZ, maxZ]

            # - Create path for L
            path_L = Part.BSplineCurve()
            path_L.approximate(Points = l_points, Continuity="C0")

            # - Create path for R
            path_R = Part.BSplineCurve()
            path_R.approximate(Points = r_points, Continuity="C0")
            
            obj.LeftSegmentLength = float(path_L.length())
            obj.RightSegmentLength = float(path_R.length())

            shapes = [path_L.toShape(), path_R.toShape(), source]

        if obj.ShowProjectionLines:
            shapes.append(Part.makeLine(l_points[START] , r_points[START]))
            shapes.append(Part.makeLine(l_points[END] , r_points[END] ))
        
        # - Update shape and information
        obj.Shape = Part.makeCompound(shapes)
        

class ProjectionSectionVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("projection.svg")

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
        if self.Object.Source is not None and len(self.Object.Source) > 0:
            return [self.Object.Source[0]]
        return None

    def doubleClicked(self, obj):
        return True
    
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
            objects = utilities.getAllSelectedObjects()
            obj = group.newObject("Part::FeaturePython","Projection")
            
            ProjectionSection(obj, 
                        (FreeCAD.ActiveDocument.getObject((objects[0])[0].Name), (objects[0])[1][0]), 
                        group.ConfigName)
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
                objects = utilities.getAllSelectedObjects()

                # - Number of edges should be two
                if len(objects) < 1:               
                    return False
                
                wp = utilities.getWorkingPlanes(group)
                if wp is None or len(wp) != 2:
                    return False                    
                return True
            return False
            
Gui.addCommand("MakeProjection", MakeProjection())
