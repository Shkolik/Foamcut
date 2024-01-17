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
import utilities

class WireEnter:
    def __init__(self, obj, entry, config):              
        obj.addProperty("App::PropertyDistance",  "SafeHeight", "Task", "Safe height" )        
        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Enter"
        obj.addProperty("App::PropertyLength",    "FieldWidth","","",5)

        obj.addProperty("App::PropertyFloat",     "PointXL",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZL",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointXR",   "", "", 1)
        obj.addProperty("App::PropertyFloat",     "PointZR",   "", "", 1)

        obj.addProperty("App::PropertyDistance",    "LeftSegmentLength",     "Information", "Left Segment length",   1)
        obj.addProperty("App::PropertyDistance",    "RightSegmentLength",     "Information", "Right Segment length",   1)

        obj.addProperty("App::PropertyLinkSub",      "EntryPoint",      "Task",   "Entry Point").EntryPoint = entry

        obj.setExpression(".SafeHeight", u"<<{}>>.SafeHeight".format(config))
        obj.setExpression(".FieldWidth", u"<<{}>>.FieldWidth".format(config))
        obj.setEditorMode("Placement", 3)
        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(self, obj):        
        parent = obj.EntryPoint[0]
        vertex = parent.getSubObject(obj.EntryPoint[1][0])

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
            point_start_L = App.Vector(-obj.FieldWidth / 2,  parent.PointXL, parent.PointZL)
            point_start_R = App.Vector( obj.FieldWidth / 2,  parent.PointXR, parent.PointZR)

            point_end_L = App.Vector(-obj.FieldWidth / 2,  parent.PointXL + float(parent.InXDirection), parent.PointZL + float(parent.InZDirection))
            point_end_R = App.Vector( obj.FieldWidth / 2,  parent.PointXR + float(parent.InXDirection), parent.PointZR + float(parent.InZDirection))

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
            App.Vector(-obj.FieldWidth / 2,  obj.PointXL, obj.SafeHeight),
            App.Vector(-obj.FieldWidth / 2,   obj.PointXL, obj.PointZL)
        )
        line_R = Part.makeLine(
            App.Vector(obj.FieldWidth / 2,  obj.PointXR, obj.SafeHeight),
            App.Vector(obj.FieldWidth / 2,   obj.PointXR, obj.PointZR)
        )
        obj.LeftSegmentLength = line_L.Length
        obj.RightSegmentLength = line_R.Length
        obj.Shape = Part.makeCompound([line_L, line_R])
        obj.ViewObject.LineColor = (0.0, 1.0, 0.0)


class WireEnterVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("enter.svg")

    def doubleClicked(self, obj):
        return True

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
            objects = utilities.getAllSelectedObjects()
            
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
                objects = utilities.getAllSelectedObjects()

                # - nothing selected
                if len(objects) == 0:
                    return False
                
                object = objects[0]
                parent = object[0]
                # - Check object type
                if parent.Type != "Path" and parent.Type != "Move":                    
                    return False
                
                wp = utilities.getWorkingPlanes(group)
                if wp is None or len(wp) != 2:
                    return False
                    
                vertex = parent.getSubObject(object[1][0])
                # Selected point should be on any working plane
                if (not wp[0].Shape.isInside(App.Vector(vertex.X, vertex.Y, vertex.Z), 0.01, True) 
                    and not wp[1].Shape.isInside(App.Vector(vertex.X, vertex.Y, vertex.Z), 0.01, True)):
                    return False
                return True
            return False
            
Gui.addCommand("MakeEnter", MakeEnter())