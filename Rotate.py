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
import FoamCutViewProviders
import FoamCutBase
import utilities
 
class Rotation(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, source, jobName): 
        super().__init__(obj, jobName)       
        obj.Type = "Rotation"  

        obj.addProperty("App::PropertyDistance",   "OriginRotationX", "", "", 5)

        obj.addProperty("App::PropertyLink",      "Source",     "Task",     "Source object").Source = source
        obj.addProperty("App::PropertyAngle",     "Angle",      "Task",     "Rotate object by angle").Angle = 90
        

        config = self.getConfigName(obj)
        obj.setExpression(".OriginRotationX", u"<<{}>>.OriginRotationX".format(config))
        
        obj.Proxy = self
        self.execute(obj)

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

class RotationVP(FoamCutViewProviders.FoamCutBaseViewProvider):   
    def getIcon(self):
        return utilities.getIconPath("rotation.svg")
    
    def claimChildren(self):
        return [self.Object.Source]

    def onDelete(self, obj, subelements):
        try:
            self.Object.Source.ViewObject.Visibility = True
        except Exception as err:
            App.Console.PrintError("Error in onDelete: {0} \n".format(err))
        return True    

class AddRotation():
    """Add Rotation"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("rotation.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Rotate target",
                "ToolTip" : "Rotate target object by given angle around rotation axis"}

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
            
            source = Gui.Selection.getSelectionEx()[0].Object      
            # - Create rotation object
            rt = FreeCAD.ActiveDocument.addObject("Part::FeaturePython", "Rotation")
            
            Rotation(rt, source, group.Name)
            RotationVP(rt.ViewObject)

            group.addObject(rt)
            Gui.Selection.clearSelection()
            FreeCAD.ActiveDocument.recompute()            
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":

                config = group.getObject(group.ConfigName)

                if not config.FiveAxisMachine:
                    return False
                
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
                
                print(obj.TypeId)

                if (hasattr(obj, "Type") and
                    (obj.Type == "Path" or obj.Type == "Enter"  or obj.Type == "Job" or obj.Type == "Helper" or obj.Type == "Config"
                    or obj.Type == "Exit" or obj.Type == "Move" or obj.Type == "Join" or obj.Type == "Route" or obj.Type == "Projection")):
                    return False
                
                return True
            return False
            
Gui.addCommand("Rotate", AddRotation())
