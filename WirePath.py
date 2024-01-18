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
from utilities import makePathByPointSets
import math



'''
  Make path on working planes by two edges, vertices, or their combination
  @param first - First edge / vertex
  @param second - Second edge / vertex
  @param step - Distance between points in edge discretization
'''
def makePathPointsByEdgesPair(first, second, planes, step = 0.1):
    # --- Use only end vertices of coplanar edges or lines because path will be a straight line
    if first.isCoplanar(second) or (first.ShapeType == "Edge" and first.Curve.TypeId == "Part::GeomLine" and  second.ShapeType == "Edge" and second.Curve.TypeId == "Part::GeomLine"):
        
        # - Synchronize edges direction
        # sometime it produces incorrect result, so one points set needs to be flipped. 
        # it's known issue, and method makePathByPointSets() accounts for it
        v00, v01, v10, v11 = utilities.getSynchronizedVertices(first, second)
        
        # - Make path
        return makePathByPointSets([v00.Point, v01.Point], [v10.Point, v11.Point], planes)

    # --- This not coplanar edges
    else:
        # - Detect vertex and vertex
        if first.ShapeType == "Vertex" and second.ShapeType == "Vertex":
            return makePathByPointSets([first.Point], [second.Point], planes)

        # - Detect line with combination of vertex or another line
        if                                                                                                                                                  \
        (first.ShapeType == "Edge" and first.Curve.TypeId == "Part::GeomLine" and second.ShapeType == "Vertex")                                             \
        or                                                                                                                                                  \
        (first.ShapeType == "Vertex" and second.ShapeType == "Edge" and second.Curve.TypeId == "Part::GeomLine")                                            \
        :
            # - Simplify path to straight line
            points_count = 2
        else:
            # - Find longest edge
            maxlen = first.Length if first.Length >= second.Length else second.Length

            # - Calculate number of discretization points
            points_count = int(float(maxlen) / float(step))

    print("Point count = %d" % points_count)

    first_set   = []
    second_set  = []

    # - Discretize first edge
    if first.ShapeType == "Vertex":
        for i in range(points_count): first_set.append(first.Point)
    else:
        first_set = first.discretize(Number=points_count) if points_count > 2 else [first.firstVertex().Point, first.lastVertex().Point]

    # - Discretize second edge
    if second.ShapeType == "Vertex":
        for i in range(points_count): second_set.append(second.Point)
    else:
        second_set = second.discretize(Number=points_count) if points_count > 2 else [second.firstVertex().Point, second.lastVertex().Point]

    # - Make path
    return makePathByPointSets(first_set, second_set, planes)

class PathSection:
    def __init__(self, obj, edge_l, edge_r, config):
        obj.addProperty("App::PropertyVectorList",  "Path_L",     "", "", 5)
        obj.addProperty("App::PropertyVectorList",  "Path_R",     "", "", 5)
        obj.addProperty("App::PropertyLength",      "FieldWidth","","",5) # - we need this field only to trigger recompute when this property changed in config
        obj.addProperty("App::PropertyString",      "Type",       "", "", 5).Type = "Path"

        obj.addProperty("App::PropertyLinkSub",     "LeftEdge",             "Edges",    "Left Edge").LeftEdge = edge_l
        obj.addProperty("App::PropertyLinkSub",     "RightEdge",            "Edges",    "Right Edge").RightEdge = edge_r
        
        obj.addProperty("App::PropertyInteger",     "PointsCount",          "Information", "Number of points", 1)
        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",    "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",   "Information", "Right Segment length",   1)
        obj.addProperty("App::PropertyBool",        "ShowProjectionLines",  "Information", "Show projection lines between planes").ShowProjectionLines = False

        obj.setExpression(".FieldWidth", u"<<{}>>.FieldWidth".format(config))

        obj.setEditorMode("Placement", 3)
        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(self, obj):
        START       = 0           # - start point index
        END         = -1          # - end point index
    
        job = obj.getParentGroup()
        # - Get working planes
        wp = utilities.getWorkingPlanes(job)
        
        if wp is None or len(wp) != 2:
            FreeCAD.Console.PrintError("ERROR:\n Error updating Path - working planes not found in Parent object '{}'\n".format(job.Label if job is not None else "None"))

        left = obj.LeftEdge[0].getSubObject(obj.LeftEdge[1])[0]
        right = obj.RightEdge[0].getSubObject(obj.RightEdge[1])[0]
        
        # - Make path between objects on working planes
        path_points = makePathPointsByEdgesPair(left, right, wp)

        # - Set data
        obj.Path_L       = [item for item in path_points[START]]
        obj.Path_R       = [item for item in path_points[END]]        
        obj.PointsCount  = int(len(path_points[START]))
        #

        # - Create path for L
        path_L = Part.BSplineCurve()
        path_L.approximate(Points = obj.Path_L, Continuity="C0")

        # - Create path for R
        path_R = Part.BSplineCurve()
        path_R.approximate(Points = obj.Path_R, Continuity="C0")

        shapes = [path_L.toShape(), path_R.toShape(), left, right]

        if obj.ShowProjectionLines:
            shapes.append(Part.makeLine(obj.Path_L[START] , obj.Path_R[START]))
            shapes.append(Part.makeLine(obj.Path_L[END] , obj.Path_R[END] ))
        
        # - Update shape and information
        obj.Shape = Part.makeCompound(shapes)
        obj.LeftSegmentLength = float(path_L.length())
        obj.RightSegmentLength = float(path_R.length())

class PathSectionVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("path.svg")

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
        if (self.Object.LeftEdge is not None and len(self.Object.LeftEdge) > 0 
            and self.Object.RightEdge is not None and len(self.Object.RightEdge) > 0 ):
            return [self.Object.LeftEdge[0], self.Object.RightEdge[0]] if self.Object.LeftEdge[0] != self.Object.RightEdge[0] else [self.Object.LeftEdge[0]]
        return None

    def doubleClicked(self, obj):
        return True
    
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
                        group.ConfigName)
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
                objects = utilities.getAllSelectedObjects()

                # - Number of edges should be two
                if len(objects) != 2:               
                    return False
                
                wp = utilities.getWorkingPlanes(group)
                if wp is None or len(wp) != 2:
                    return False                    
                return True
            return False
            
Gui.addCommand("MakePath", MakePath())
