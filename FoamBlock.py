# -*- coding: utf-8 -*-

__title__ = "Foam Block"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Foam block representation."

__obsolete__ = True  # Kept only for old-document restore/migration; pending removal.

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
        
        job = utilities.getJob(obj)
        
        utilities.bindJob(obj, job)
        obj.setExpression(".Width",   utilities.jobExpression(job, "BlockWidth"))
        obj.setExpression(".Length",  utilities.jobExpression(job, "BlockLength"))
        obj.setExpression(".Height",  utilities.jobExpression(job, "BlockHeight"))

        obj.setExpression(".Placement.Base.x", utilities.jobExpression(job, "BlockPosition") + ".x")
        obj.setExpression(".Placement.Base.y", utilities.jobExpression(job, "BlockPosition") + ".y")
        obj.setExpression(".Placement.Base.z", utilities.jobExpression(job, "BlockPosition") + ".z")
        
        obj.Proxy = self

        self.execute(obj)

    def onDocumentRestored(self, obj):
        utilities.setPickStyle(obj.ViewObject, utilities.UNPICKABLE)

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
        obj.Selectable = False

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        utilities.setPickStyle(obj, utilities.UNPICKABLE)

    def getIcon(self):
        return utilities.getIconPath("block.svg")    
    
def CreateFoamBlock(obj, jobName):
    FoamBlock(obj, jobName)
    FoamBlockVP(obj.ViewObject)

