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
 
class FoamBlock:
    def __init__(self, obj, config):        
        obj.addProperty("App::PropertyString",    "Type", "", "", 5).Type = "Helper"  
        obj.addProperty("App::PropertyLength",     "Length", "", "", 5).Length = 100                            
        obj.addProperty("App::PropertyLength",     "Width", "", "", 5).Width = 100  
        obj.addProperty("App::PropertyLength",     "Height", "", "", 5).Height = 100      
        
        obj.setExpression(".Width",   u"<<{}>>.BlockWidth".format(config))
        obj.setExpression(".Length",  u"<<{}>>.BlockLength".format(config))
        obj.setExpression(".Height",  u"<<{}>>.BlockHeight".format(config))

        obj.setExpression(".Placement.Base.x", u"<<{}>>.BlockPosition.x".format(config))
        obj.setExpression(".Placement.Base.y", u"<<{}>>.BlockPosition.y".format(config))
        obj.setExpression(".Placement.Base.z", u"<<{}>>.BlockPosition.z".format(config))
        
        obj.setEditorMode("Placement", 3)

        obj.Proxy = self

        self.execute(obj)
        Gui.Selection.clearSelection()

    def onChanged(this, fp, prop):
        pass

    def execute(self, obj):
        xdir = App.Vector(0.0, 0.0, 1.0)
        block = Part.makeBox(obj.Width, obj.Length, obj.Height, App.Vector(0.0, 0.0, 0.0), xdir)
        
        obj.Shape     = block
        
class FoamBlockVP:
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
    
def CreateFoamBlock(obj, config):
    FoamBlock(obj, config)
    FoamBlockVP(obj.ViewObject)