# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Rotate selected body."
__usage__ = """Select target body to rotate and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import utilities
 
class Rotation:
    def __init__(self, obj, source, config):        
        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Rotation"  

        obj.addProperty("App::PropertyLink",      "Source",      "Task",   "Source object").Source = source
        obj.addProperty("App::PropertyAngle",     "Angle",      "Task", "Rotate object by angle").Angle = 90
        obj.addProperty("App::PropertyDistance",   "OriginRotationX", "", "", 5)
        obj.setExpression(".OriginRotationX", u"<<{}>>.OriginRotationX".format(config))
        obj.setEditorMode("Placement", 3)
        obj.Proxy = self

        self.execute(obj)

    def onChanged(this, fp, prop):
        # FreeCAD.Console.PrintMessage("Change property: " + str(prop) + "\n")
        pass

    def execute(self, obj):
        if obj.Source is None:
            return

        obj.Source.ViewObject.Visibility = False

        # - Copy and rotate object
        shape = obj.Source.Shape.copy()
        shape.rotate(App.Vector(0.0, obj.OriginRotationX, 0.0), App.Vector(0,0,1), obj.Angle)
        
        # - Assign new shape
        obj.Shape     = shape
        obj.Placement = shape.Placement

class RotationVP:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("rotation.svg")

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
        return [self.Object.Source]

    def onDelete(self, feature, subelements):
        try:
            self.Object.Source.ViewObject.Visibility = True
        except Exception as err:
            FreeCAD.Console.PrintError("Error in onDelete: {0} \n".format(err))
        return True
    
    def doubleClicked(self, obj):
        return True

class AddRotation():
    """Add Rotation"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("rotation.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Rotate target",
                "ToolTip" : "Rotate target object by given angle"}

    def Activated(self):   
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":
            source = Gui.Selection.getSelectionEx()[0].Object      
            # - Create rotation object
            rt = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Rotation")
            
            Rotation(rt, source, group.ConfigName)
            RotationVP(rt.ViewObject)

            group.addObject(rt)
            rt.recompute()
            Gui.Selection.clearSelection()
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            if group is not None and group.Type == "Job":
                # - Get selecttion
                selection = Gui.Selection.getSelectionEx()

                # - nothing selected
                if len(selection) == 0:
                    return False
                
                # - Check object type
                if selection[0] is None or selection[0].Object is None:                    
                    return False      

                obj = selection[0].Object
                if not hasattr(obj, "Shape"):
                    return False
                if ((obj.TypeId == "Part::FeaturePython" or obj.TypeId == "App::DocumentObjectGroupPython") and 
                    (obj.Type == "Path" or obj.Type == "Enter"  or obj.Type == "Job" or obj.Type == "Helper"
                    or obj.Type == "Exit" or obj.Type == "Move" or obj.Type == "Join" or obj.Type == "Route")):
                    return False
                
                return True
            return False
            
Gui.addCommand("Rotate", AddRotation())
