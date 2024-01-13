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
import utilities

class Join:
    def __init__(self, obj, start, end, config):  

        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Join"
        obj.addProperty("App::PropertyLength",    "FieldWidth","","",5)

        # - Options
        obj.addProperty("App::PropertySpeed",     "FeedRate",  "Options",  "Feed rate" )
        obj.addProperty("App::PropertyInteger",   "WirePower", "Options",  "Wire power")

        obj.addProperty("App::PropertyFloat",     "PointXLA",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZLA",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointXRA",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZRA",   "", "", 1)

        obj.addProperty("App::PropertyFloat",     "PointXLB",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZLB",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointXRB",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZRB",   "", "", 1)

        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",     "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",     "Information", "Right Segment length",   1)

        obj.addProperty("App::PropertyLinkSub",      "StartPoint",      "Task",   "Start Point").StartPoint = start
        obj.addProperty("App::PropertyLinkSub",      "EndPoint",      "Task",   "Start Point").EndPoint = end

        obj.setExpression(".FeedRate", u"<<{}>>.FeedRateCut".format(config))
        obj.setExpression(".WirePower", u"<<{}>>.WireMinPower".format(config))
        obj.setExpression(".FieldWidth", u"<<{}>>.FieldWidth".format(config))
        obj.setEditorMode("Placement", 3)        
        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(self, obj):
        parentA = obj.StartPoint[0]
        vertexA = parentA.getSubObject(obj.StartPoint[1][0])

        parentB = obj.EndPoint[0]
        vertexB = parentB.getSubObject(obj.EndPoint[1][0])

        pointA = App.Vector(
            vertexA.X,
            vertexA.Y,
            vertexA.Z
        )

        pointB = App.Vector(
            vertexB.X,
            vertexB.Y,
            vertexB.Z
        )

        if parentA.Type == "Path":
            # - Connect
            if utilities.isCommonPoint(parentA.Path_L[0], pointA) or utilities.isCommonPoint(parentA.Path_R[0], pointA):
                # - Forward direction
                obj.PointXLA = parentA.Path_L[0].y
                obj.PointZLA = parentA.Path_L[0].z
                obj.PointXRA = parentA.Path_R[0].y
                obj.PointZRA = parentA.Path_R[0].z

            elif utilities.isCommonPoint(parentA.Path_L[-1], pointA) or utilities.isCommonPoint(parentA.Path_R[-1], pointA):
                # - Forward direction
                obj.PointXLA = parentA.Path_L[-1].y
                obj.PointZLA = parentA.Path_L[-1].z
                obj.PointXRA = parentA.Path_R[-1].y
                obj.PointZRA = parentA.Path_R[-1].z

        elif parentA.Type == "Move":
            point_start_L = App.Vector(-obj.FieldWidth / 2,  parentA.PointXL, parentA.PointZL)
            point_start_R = App.Vector( obj.FieldWidth / 2,  parentA.PointXR, parentA.PointZR)

            point_end_L = App.Vector(-obj.FieldWidth / 2,  parentA.PointXL + float(parentA.InXDirection), parentA.PointZL + float(parentA.InZDirection))
            point_end_R = App.Vector( obj.FieldWidth / 2,  parentA.PointXR + float(parentA.InXDirection), parentA.PointZR + float(parentA.InZDirection))

            # - Connect
            if utilities.isCommonPoint(point_start_L, pointA) or utilities.isCommonPoint(point_start_R, pointA):
                # - Forward direction
                obj.PointXLA = point_start_L.y
                obj.PointZLA = point_start_L.z
                obj.PointXRA = point_start_R.y
                obj.PointZRA = point_start_R.z

            elif utilities.isCommonPoint(point_end_L, pointA) or utilities.isCommonPoint(point_end_R, pointA):
                # - Backward direction
                obj.PointXLA = point_end_L.y
                obj.PointZLA = point_end_L.z
                obj.PointXRA = point_end_R.y
                obj.PointZRA = point_end_R.z

        if parentB.Type == "Path":
            # - Connect
            if utilities.isCommonPoint(parentB.Path_L[0], pointB) or utilities.isCommonPoint(parentB.Path_R[0], pointB):
                # - Forward direction
                obj.PointXLB = parentB.Path_L[0].y
                obj.PointZLB = parentB.Path_L[0].z
                obj.PointXRB = parentB.Path_R[0].y
                obj.PointZRB = parentB.Path_R[0].z
            elif utilities.isCommonPoint(parentB.Path_L[-1], pointB) or utilities.isCommonPoint(parentB.Path_R[-1], pointB):
                # - Forward direction
                obj.PointXLB = parentB.Path_L[-1].y
                obj.PointZLB = parentB.Path_L[-1].z
                obj.PointXRB = parentB.Path_R[-1].y
                obj.PointZRB = parentB.Path_R[-1].z

        elif parentB.Type == "Move":
            point_start_L = App.Vector(-obj.FieldWidth / 2,  parentB.PointXL, parentB.PointZL)
            point_start_R = App.Vector( obj.FieldWidth / 2,  parentB.PointXR, parentB.PointZR)

            point_end_L = App.Vector(-obj.FieldWidth / 2,  parentB.PointXL + float(parentB.InXDirection), parentB.PointZL + float(parentB.InZDirection))
            point_end_R = App.Vector( obj.FieldWidth / 2,  parentB.PointXR + float(parentB.InXDirection), parentB.PointZR + float(parentB.InZDirection))

            # - Connect
            if utilities.isCommonPoint(point_start_L, pointB) or utilities.isCommonPoint(point_start_R, pointB):
                # - Forward direction
                obj.PointXLB = point_start_L.y
                obj.PointZLB = point_start_L.z
                obj.PointXRB = point_start_R.y
                obj.PointZRB = point_start_R.z

            elif utilities.isCommonPoint(point_end_L, pointB) or utilities.isCommonPoint(point_end_R, pointB):
                # - Forward direction
                obj.PointXLB = point_end_L.y
                obj.PointZLB = point_end_L.z
                obj.PointXRB = point_end_R.y
                obj.PointZRB = point_end_R.z
                
        line_L = Part.makeLine(
            App.Vector(-obj.FieldWidth / 2,  obj.PointXLA, obj.PointZLA),
            App.Vector(-obj.FieldWidth / 2,  obj.PointXLB, obj.PointZLB)
        )
        line_R = Part.makeLine(
            App.Vector(obj.FieldWidth / 2,   obj.PointXRA, obj.PointZRA),
            App.Vector(obj.FieldWidth / 2,   obj.PointXRB, obj.PointZRB)
        )
        obj.LeftSegmentLength = line_L.Length
        obj.RightSegmentLength = line_R.Length
        obj.Shape = Part.makeCompound([line_L, line_R])
        obj.ViewObject.LineColor = (0.137, 0.0, 0.803)

        Gui.Selection.clearSelection()

class JoinVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("join.svg")

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
        return [self.Object.StartPoint[0], self.Object.EndPoint[0]]

    def onDelete(self, feature, subelements):
        try:
            self.Object.StartPoint[0].ViewObject.Visibility = True
            self.Object.EndPoint[0].ViewObject.Visibility = True
        except Exception as err:
            FreeCAD.Console.PrintError("Error in onDelete: {0} \n".format(err))
        return True

class MakeJoin():
    """Make Join"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("join.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Join 2 points",
                "ToolTip" : "Join 2 selected coplanar points"}

    def Activated(self):         
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":    
            # - Get selecttion
            objects = utilities.getAllSelectedObjects()
            
            # - Create object
            join = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Join")
            Join(join, objects[0], objects[1], group.ConfigName)
            JoinVP(join.ViewObject)
            join.ViewObject.PointSize = 4
    
            group.addObject(join)

            FreeCAD.ActiveDocument.recompute()
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            if group is not None and group.Type == "Job":   
                # - Get selecttion
                objects = utilities.getAllSelectedObjects()

                # - nothing selected
                if len(objects) < 2:
                    return False
                
                objectA = objects[0]
                parentA = objectA[0]
                objectB = objects[1]
                parentB = objectB[0]
                # - Check object type
                if parentA.Type != "Path" and parentA.Type != "Move":                    
                    return False
                
                wp = utilities.getWorkingPlanes()
                if len(wp) != 2:
                    return False
                    
                vertexA = parentA.getSubObject(objectA[1][0])
                vertexB = parentB.getSubObject(objectB[1][0])
                # Selected point should be on any working plane
                if (not wp[0].Shape.isInside(App.Vector(vertexA.X, vertexA.Y, vertexA.Z), 0.01, True) 
                    and not wp[1].Shape.isInside(App.Vector(vertexA.X, vertexA.Y, vertexA.Z), 0.01, True)):
                    return False
                if (not wp[0].Shape.isInside(App.Vector(vertexB.X, vertexB.Y, vertexB.Z), 0.01, True) 
                    and not wp[1].Shape.isInside(App.Vector(vertexB.X, vertexB.Y, vertexB.Z), 0.01, True)):
                    return False
                return True
            return False
            
Gui.addCommand("Join", MakeJoin())
