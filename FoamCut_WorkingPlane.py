# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Working plane."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutBase
import FoamCutViewProviders
import utilities
import Part
 
class FoamCutWorkingPlane(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName, side):     
        super().__init__(obj, jobName)       
        obj.Type = "Helper"  
        obj.addProperty("App::PropertyLength",     "Length", "", "", 5).Length = 100                                         # Machine X axis
        obj.addProperty("App::PropertyLength",     "Width", "", "", 5).Width = 100                                          # Machine Y axis
        obj.addProperty("App::PropertyPosition",   "Position", "", "", 5).Position = App.Vector(0.0, 0.0, 0.0)  # Machine base X axis
        
        config = self.getConfigName(obj)

        obj.setExpression(".Width",   u"<<{}>>.VerticalTravel".format(config))
        obj.setExpression(".Length",  u"<<{}>>.HorizontalTravel".format(config))

        obj.setExpression(".Position.y", u"-<<{}>>.OriginX".format(config))
        
        if side == utilities.LEFT:
            obj.setExpression(".Position.x", u"-<<{}>>.FieldWidth / 2".format(config))
        else:
            obj.setExpression(".Position.x", u"<<{}>>.FieldWidth / 2".format(config))

        obj.Proxy = self

        self.execute(obj)
        # Gui.Selection.clearSelection()

    def execute(self, obj):
        norm = App.Vector(1.0, 0.0, 0.0)
        xdir = App.Vector(0.0, 1.0, 0.0)
        plane = Part.makePlane(obj.Length, obj.Width, obj.Position, norm, xdir)
        
        obj.Shape     = plane
        obj.Placement = plane.Placement
        
class FoamCutWorkingPlaneVP(FoamCutViewProviders.FoamCutBaseViewProvider):   
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
    
    
def CreateWorkingPlane(obj, jobName, side):
    FoamCutWorkingPlane(obj, jobName, side)
    FoamCutWorkingPlaneVP(obj.ViewObject)