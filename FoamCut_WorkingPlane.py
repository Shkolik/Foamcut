# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Working plane."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import utilities
import Part
 
class FoamCutWorkingPlane:
    def __init__(self, obj, config, side):        
        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Helper"  
        obj.addProperty("App::PropertyLength",     "Length", "", "", 5).Length = 100                                         # Machine X axis
        obj.addProperty("App::PropertyLength",     "Width", "", "", 5).Width = 100                                          # Machine Y axis
        obj.addProperty("App::PropertyPosition",   "Position", "", "", 5).Position = App.Vector(0.0, 0.0, 0.0)  # Machine base X axis
        
        obj.setExpression(".Width",   u"<<{}>>.VerticalTravel".format(config))
        obj.setExpression(".Length",  u"<<{}>>.HorizontalTravel".format(config))

        obj.setExpression(".Position.y", u"-<<{}>>.OriginX".format(config))
        
        if side == utilities.LEFT:
            obj.setExpression(".Position.x", u"-<<{}>>.FieldWidth / 2".format(config))
        else:
            obj.setExpression(".Position.x", u"<<{}>>.FieldWidth / 2".format(config))

        obj.setEditorMode("Placement", 3)
        obj.Proxy = self

        self.execute(obj)
        Gui.Selection.clearSelection()

    def onChanged(this, fp, prop):
        pass

    def execute(self, obj):
        norm = App.Vector(1.0, 0.0, 0.0)
        xdir = App.Vector(0.0, 1.0, 0.0)
        plane = Part.makePlane(obj.Length, obj.Width, obj.Position, norm, xdir)
        
        obj.Shape     = plane
        obj.Placement = plane.Placement
        
class FoamCutWorkingPlaneVP:
    def __init__(self, obj):
        obj.LineColor  =  (255, 225, 5)
        obj.ShapeColor = (255, 225, 5)
        obj.PointColor = (255, 225, 5)
        obj.LineWidth  = 1
        obj.PointSize  = 1
        obj.Proxy = self
        obj.Transparency = 80

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

    def getIcon(self):
        return utilities.getIconPath("plane.svg")
    
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
    
def CreateWorkingPlane(obj, config, side):
    FoamCutWorkingPlane(obj, config, side)
    FoamCutWorkingPlaneVP(obj.ViewObject)