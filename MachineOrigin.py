# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Origin arrors and labels."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import FoamCutBase
import FoamCutViewProviders
import utilities
import math
import pivy.coin as coin

class MachineOrigin(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):
        super().__init__(obj, jobName)     
        obj.Type = "Helper"

        obj.addProperty("App::PropertyDistance", "FieldWidth", "", "", 5)
        
        config = self.getConfig(obj)

        obj.FieldWidth = config.FieldWidth
        obj.setExpression(".FieldWidth", u"<<{}>>.FieldWidth".format(config.Name))

        obj.Proxy = self

class MachineOriginVP(FoamCutViewProviders.FoamCutBaseViewProvider):    
    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

        self.x_axis_so_color = coin.SoBaseColor()
        self.x_axis_so_color.rgb.setValue(0, 1, 0)
        self.y_axis_so_color = coin.SoBaseColor()
        self.y_axis_so_color.rgb.setValue(1, 0, 0)
        
        self.axisScale = coin.SoScale()
        self.axisScale.scaleFactor.setValue(1, 1, 1)
        
        self.draw_style = coin.SoDrawStyle()
        self.draw_style.style = coin.SoDrawStyle.FILLED
        self.draw_style.lineWidth = 3
        
        self.transformL = coin.SoTransform()
        self.transformR = coin.SoTransform()
        
        self.origL = self.drawOrigin(self.transformL, False)
        self.origR = self.drawOrigin(self.transformR, True)
        
        self.node = coin.SoGroup()
        self.node.addChild(self.origL)
        self.node.addChild(self.origR)

        obj.addDisplayMode(self.node, "Flat Lines")

    def getIcon(self):
        return utilities.getIconPath("origin.svg")
    
    def updateData(self, obj, prop):
        if prop == "FieldWidth" and obj.FieldWidth:
            self.updatePlacement(self.transformL, -float(obj.FieldWidth/2))
            self.updatePlacement(self.transformR, float(obj.FieldWidth/2))
        
    def getDisplayModes(self, obj):
        """Return the display modes that this viewprovider supports."""
        return ["Flat Lines"]
    
    def drawAxis(self, string, length, rotate, mirror, soColor):
        line = coin.SoLineSet()
        line.numVertices.setValue(2)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, [[0, 0, 0], [0, length, 0]])

        cone=coin.SoCone()
        cone.bottomRadius= 2
        cone.height= 10

        font = coin.SoFont()
        font.name = "Arial"
        font.size = 10.0

        text = coin.SoAsciiText()
        text.string = string

        text_transform = coin.SoTransform()
        rotation_x = coin.SbRotation(coin.SbVec3f(1, 0, 0), math.radians(0 if rotate else 90))
        rotation_y = coin.SbRotation(coin.SbVec3f(0, 1, 0), math.radians(270))
        text_transform.rotation.setValue(rotation_y * rotation_x)
        if mirror:
            text_transform.translation = (0, -5, -5) if rotate else (0, -5, 5)
            text_transform.scaleFactor.setValue(-1, 1, 1)
        else:
            text_transform.translation = (0, -5, -15) if rotate else (0, 5, 5)
            text_transform.scaleFactor.setValue(1, 1, 1)

        shapeHints = coin.SoShapeHints()
        shapeHints.vertexOrdering = coin.SoShapeHints.CLOCKWISE if mirror else coin.SoShapeHints.COUNTERCLOCKWISE

        cone_transform = coin.SoTransform()
        cone_transform.translation = (0, length, 0)

        rotation_transform = coin.SoTransform()
        rotation_transform.rotation.setValue(coin.SbVec3f(1, 0, 0), math.radians(90 if rotate else 0))

        text_node = coin.SoGroup()
        text_node.addChild(text_transform)
        text_node.addChild(font)
        text_node.addChild(shapeHints)
        text_node.addChild(text)
        

        axis_node = coin.SoGroup()
        axis_node.addChild(rotation_transform)

        axis_sep = coin.SoSeparator()
        axis_sep.addChild(self.axisScale)
        axis_sep.addChild(self.draw_style)
        axis_sep.addChild(soColor)
        axis_sep.addChild(coords)
        axis_sep.addChild(line)

        axis_sep.addChild(cone_transform)
        axis_sep.addChild(cone)
        axis_sep.addChild(text_node)
        

        axis_node.addChild(axis_sep)
        
        return axis_node
    
    def drawOrigin(self, soTransform, isRight):
        sep = coin.SoSeparator()
        sep.addChild(soTransform)

        X_axis_sep = self.drawAxis("XR" if isRight else "XL", 100, False, isRight, self.x_axis_so_color)
        Y_axis_sep = self.drawAxis("YR" if isRight else "YL", 100, True, isRight, self.y_axis_so_color)

        sep.addChild(X_axis_sep)
        sep.addChild(Y_axis_sep)

        return sep
      
    def updatePlacement(self, soTransform, x_coord):    
        soTransform.translation.setValue(x_coord, 0, 0)
    
    
'''
    Creates Origin
    @param obj - Origin object
    @param config - config object name
'''
def CreateOrigin(obj, jobName):
    MachineOrigin(obj, jobName)
    MachineOriginVP(obj.ViewObject)
    utilities.setPickStyle(obj.ViewObject, utilities.UNPICKABLE)
    Gui.Selection.clearSelection()