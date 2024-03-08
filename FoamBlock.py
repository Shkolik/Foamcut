# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Working plane."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutViewProviders
import FoamCutBase
import utilities
import Part
 
class FoamBlock(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):   
        super().__init__(obj, jobName)       
        obj.Type = "Helper"  
        obj.addProperty("App::PropertyLength",     "Length", "", "", 5).Length = 100                            
        obj.addProperty("App::PropertyLength",     "Width", "", "", 5).Width = 100  
        obj.addProperty("App::PropertyLength",     "Height", "", "", 5).Height = 100      
        
        config = self.getConfigName(obj)
        obj.setExpression(".Width",   u"<<{}>>.BlockWidth".format(config))
        obj.setExpression(".Length",  u"<<{}>>.BlockLength".format(config))
        obj.setExpression(".Height",  u"<<{}>>.BlockHeight".format(config))

        obj.setExpression(".Placement.Base.x", u"<<{}>>.BlockPosition.x".format(config))
        obj.setExpression(".Placement.Base.y", u"<<{}>>.BlockPosition.y".format(config))
        obj.setExpression(".Placement.Base.z", u"<<{}>>.BlockPosition.z".format(config))
        
        obj.Proxy = self

        self.execute(obj)

    def execute(self, obj):
        xdir = App.Vector(0.0, 0.0, 1.0)
        block = Part.makeBox(obj.Width, obj.Length, obj.Height, App.Vector(0.0, 0.0, 0.0), xdir)
        
        obj.Shape     = block
        
class FoamBlockVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    def __init__(self, obj):
        obj.ShapeColor = (250, 150, 125)
        obj.LineWidth  = 1
        obj.PointSize  = 1
        obj.Proxy = self
        obj.Transparency = 80

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        utilities.setPickStyle(obj, utilities.UNPICKABLE)

    def getIcon(self):
        return utilities.getIconPath("block.svg")    
    
def CreateFoamBlock(obj, jobName):
    FoamBlock(obj, jobName)
    FoamBlockVP(obj.ViewObject)