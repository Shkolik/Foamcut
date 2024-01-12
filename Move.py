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
import utilities

class Move:
    def __init__(self, obj, start):  
        # - Get CNC configuration
        config = FreeCAD.ActiveDocument.getObjectsByLabel('Config')[0]

        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Move"

        # - Options
        obj.addProperty("App::PropertyDistance",  "InXDirection",  "Options",   "Move along X axis" ).InXDirection = 100
        obj.addProperty("App::PropertyDistance",  "InZDirection",  "Options",   "Move along Z axis" ).InZDirection = 100
        obj.addProperty("App::PropertySpeed",     "FeedRate",  "Options",  "Feed rate").FeedRate = config.FeedRateCut
        obj.addProperty("App::PropertyInteger",   "WirePower", "Options",  "Wire power").WirePower = config.WireMinPower

        obj.addProperty("App::PropertyFloat",     "PointXL",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZL",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointXR",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZR",   "", "", 1)

        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",     "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",     "Information", "Right Segment length",   1)

        obj.addProperty("App::PropertyLinkSub",      "StartPoint",      "Task",   "Start Point").StartPoint = start

        obj.setEditorMode("Placement", 3)
        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(self, obj):
        # - Get CNC configuration
        config = FreeCAD.ActiveDocument.getObjectsByLabel('Config')[0]

        parent = obj.StartPoint[0]
        vertex = parent.getSubObject(obj.StartPoint[1][0])

        point = App.Vector(
            vertex.X,
            vertex.Y,
            vertex.Z
        )

        if parent.Type == "Path":
            # - Connect
            if utilities.isCommonPoint(parent.Path_L[0], point) or utilities.isCommonPoint(parent.Path_R[0], point):
                # - Forward direction
                obj.PointXL = parent.Path_L[0].y
                obj.PointZL = parent.Path_L[0].z
                obj.PointXR = parent.Path_R[0].y
                obj.PointZR = parent.Path_R[0].z

            elif utilities.isCommonPoint(parent.Path_L[-1], point) or utilities.isCommonPoint(parent.Path_R[-1], point):
                # - Backward direction
                obj.PointXL = parent.Path_L[-1].y
                obj.PointZL = parent.Path_L[-1].z
                obj.PointXR = parent.Path_R[-1].y
                obj.PointZR = parent.Path_R[-1].z

        elif parent.Type == "Move":
            point_start_L = App.Vector(-config.FieldWidth / 2,  parent.PointXL, parent.PointZL)
            point_start_R = App.Vector( config.FieldWidth / 2,  parent.PointXR, parent.PointZR)

            point_end_L = App.Vector(-config.FieldWidth / 2,  parent.PointXL + float(parent.InXDirection), parent.PointZL + float(parent.InZDirection))
            point_end_R = App.Vector( config.FieldWidth / 2,  parent.PointXR + float(parent.InXDirection), parent.PointZR + float(parent.InZDirection))

            # - Connect
            if utilities.isCommonPoint(point_start_L, point) or utilities.isCommonPoint(point_start_R, point):
                # - Forward direction
                obj.PointXL = point_start_L.y
                obj.PointZL = point_start_L.z
                obj.PointXR = point_start_R.y
                obj.PointZR = point_start_R.z

            elif utilities.isCommonPoint(point_end_L, point) or utilities.isCommonPoint(point_end_R, point):
                # - Backward direction
                obj.PointXL = point_end_L.y
                obj.PointZL = point_end_L.z
                obj.PointXR = point_end_R.y
                obj.PointZR = point_end_R.z
                
        line_L = Part.makeLine(
            App.Vector(-config.FieldWidth / 2,  obj.PointXL, obj.PointZL),
            App.Vector(-config.FieldWidth / 2,  obj.PointXL + float(obj.InXDirection.getValueAs("mm")), obj.PointZL + obj.InZDirection.getValueAs("mm"))
        )
        line_R = Part.makeLine(
            App.Vector(config.FieldWidth / 2,   obj.PointXR, obj.PointZR),
            App.Vector(config.FieldWidth / 2,   obj.PointXR + float(obj.InXDirection.getValueAs("mm")), obj.PointZR + obj.InZDirection.getValueAs("mm"))
        )
        obj.LeftSegmentLength = line_L.Length
        obj.RightSegmentLength = line_R.Length
        obj.Shape = Part.makeCompound([line_L, line_R])
        obj.ViewObject.LineColor = (0.137, 0.662, 0.803)

class MoveVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("move.svg")

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
        return [self.Object.StartPoint[0]]

    def onDelete(self, feature, subelements):
        try:
            self.Object.StartPoint[0].ViewObject.Visibility = True
        except Exception as err:
            FreeCAD.Console.PrintError("Error in onDelete: {0} \n".format(err))
        return True

class MakeMove():
    """Make Move"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("move.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create move path",
                "ToolTip" : "Create move path object from selected point in specified direction"}

    def Activated(self):         
        # - Get selecttion
        objects = utilities.getAllSelectedObjects()
        
        # - Create object
        move = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Move")
        Move(move, objects[0])
        MoveVP(move.ViewObject)
        move.ViewObject.PointSize = 4
   
        FreeCAD.ActiveDocument.recompute()
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            # - Get selecttion
            objects = utilities.getAllSelectedObjects()

            # - nothing selected
            if len(objects) == 0:
                return False
            
            object = objects[0]
            parent = object[0]
            # - Check object type
            if parent.Type != "Path" and parent.Type != "Move":                    
                return False
            
            wp = utilities.getWorkingPlanes()
            if len(wp) != 2:
                return False
                
            vertex = parent.getSubObject(object[1][0])
            # Selected point should be on any working plane
            if (not wp[0].Shape.isInside(App.Vector(vertex.X, vertex.Y, vertex.Z), 0.01, True) 
                and not wp[1].Shape.isInside(App.Vector(vertex.X, vertex.Y, vertex.Z), 0.01, True)):
                return False
            return True
            
Gui.addCommand("MakeMove", MakeMove())
