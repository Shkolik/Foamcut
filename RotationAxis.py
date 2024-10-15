# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Rotation axis helper object."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutViewProviders
import FoamCutBase
import utilities
import pivy.coin as coin
 
class RotationAxis(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):   
        super().__init__(obj, jobName)       
        obj.Type = "RotationAxis"  

        config = self.getConfigName(obj)

        obj.addProperty("App::PropertyLength",     "Length", "", "", 5)                         
        obj.addProperty("App::PropertyLength",     "Origin", "", "", 5)

        obj.setExpression(".Origin", u"<<{}>>.OriginRotationX".format(config))
        obj.setExpression(".Length", u"<<{}>>.VerticalTravel + 50mm".format(config))
        
        obj.Proxy = self

        self.execute(obj)

    def execute(self, obj):
        pass
        
class RotationAxisVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    def attach(self, obj):
        super().attach(obj)

        self.axis_color = coin.SoMaterial()
        self.axis_color.diffuseColor.setValue(1.0, 0.886, 0.023)
        self.axis_color.transparency.setValue(0.7)

        self.draw_style = coin.SoDrawStyle()
        self.draw_style.style = coin.SoDrawStyle.FILLED
        self.draw_style.lineWidth = 2
        
        line = coin.SoLineSet()
        line.numVertices.setValue(2)
        self.coords = coin.SoCoordinate3()
        
        self.updateLine()

        self.node = coin.SoSeparator()
        self.node.addChild(self.draw_style)
        self.node.addChild(self.axis_color)
        self.node.addChild(self.coords)
        self.node.addChild(line)

        obj.addDisplayMode(self.node, "Flat Lines")

        return 

    def getIcon(self):
        return utilities.getIconPath("rotation_axis.svg")    
    
    def updateData(self, obj, prop):
        if (prop == "Length" or prop == "Origin") and obj.Length and obj.Origin:
            self.updateLine()

    def updateLine(self):
        points = [(0, self.Object.Origin, 0), (0, self.Object.Origin, self.Object.Length )]
        self.coords.point.setValues(0, points)

    def getDisplayModes(self, obj):
        """Return the display modes that this viewprovider supports."""
        return ["Flat Lines"]
    
    
def CreateRotationAxis(obj, jobName):
    RotationAxis(obj, jobName)
    RotationAxisVP(obj.ViewObject)