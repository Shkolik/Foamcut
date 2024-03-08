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
import Draft
import utilities
import os

class MachineOrigin(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, jobName):
        super().__init__(obj, jobName)     
        obj.Type = "Helper"
        
        config = self.getConfigName(obj)
        obj.Group = self.createGroup(config)
        
        obj.setEditorMode("Group", 3)

        obj.Proxy = self

    def execute(self, obj):
        for item in obj.Group:
            item.recompute()

    '''
        Creates Origin arrow either X or Y
        @param x - if set to True - create X arrow, else Y
        @param x_expr   - expression to get X coordinate
    '''
    def createArrow(self, x, x_expr):
        pl = FreeCAD.Placement()
        pl.Base = FreeCAD.Vector(0.0, 0.0, 0.0)    
        points = [FreeCAD.Vector(0.0, 0.0, 0.0), FreeCAD.Vector(0.0, 100.0, 0.0)] if x else [FreeCAD.Vector(0.0, 0.0, 0.0), FreeCAD.Vector(0.0, 0.0, 100.0)]
        line = Draft.make_wire(points, placement=pl, closed=False, face=False, support=None)
        line.setExpression(".Placement.Base.x", x_expr)
        line.setExpression(".Start.x", x_expr)
        line.setExpression(".End.x", x_expr)
        line.End.y = 100.0 if x else 0.0
        line.End.z = 0.0 if x else 100.0
        if x:
            line.ViewObject.LineColor = (0,170,0)
            line.ViewObject.PointColor = (0,170,0)
            
        else:
            line.ViewObject.LineColor = (170,0,0)
            line.ViewObject.PointColor = (170,0,0)

        line.ViewObject.LineWidth = 2
        line.ViewObject.PointSize = 1
        line.ViewObject.ArrowSize = 3
        line.ViewObject.ArrowType = u"Arrow"
        line.ViewObject.EndArrow = True
        line.ViewObject.ShowInTree = False
        line.recompute()
        return line

    '''
        Creates Origin arrow label
        @param x        - if set to True - create X arrow label, else Y
        @param x_expr   - expression to get X coordinate
        @param position - -1 (LEFT) or 1 (RIGHT)
    '''
    def createLabel(self, x, x_expr, position):
        pl = FreeCAD.Placement()
        pl.Base = FreeCAD.Vector(0.0, 100.0, 8.0) if x else FreeCAD.Vector(0.0, 16.0, 90.0)
        pl.Rotation.Q = (0.5, -0.5, -0.5, 0.5) if position == utilities.LEFT else (0.5, 0.5, 0.5, 0.5)

        str = ("X" if x else "Y") + ("L" if position == utilities.LEFT else "R")
        font = os.path.join(utilities.getResourcesPath(), "calibri.ttf")
        ss = Draft.make_shapestring(String=str, FontFile=font, Size=10.0, Tracking=0.0)
        ss.Placement = pl
        ss.setExpression(".Placement.Base.x", x_expr)
        # ss.Support=None
        ss.ViewObject.ShowInTree = False
        if x:
            ss.ViewObject.ShapeColor = (0,170,0)
            ss.ViewObject.LineColor = (0,170,0)
            ss.ViewObject.PointColor = (0,170,0)            
        else:
            ss.ViewObject.ShapeColor = (170,0,0)
            ss.ViewObject.LineColor = (170,0,0)
            ss.ViewObject.PointColor = (170,0,0)
        return ss

    '''
        Creates group of children
        @param config - config object name
        @returns - list of child objects
    '''
    def createGroup(self, config):    
        x_expr_l = u"-<<{}>>.FieldWidth / 2".format(config) 
        x_expr_r = u"<<{}>>.FieldWidth / 2".format(config)  
        return [
            self.createArrow(True, x_expr_l), self.createArrow(False, x_expr_l), self.createLabel(True, x_expr_l, utilities.LEFT), self.createLabel(False, x_expr_l, utilities.LEFT),
            self.createArrow(True, x_expr_r), self.createArrow(False, x_expr_r), self.createLabel(True, x_expr_r, utilities.RIGHT), self.createLabel(False, x_expr_r, utilities.RIGHT)
            ]


class MachineOriginVP(FoamCutViewProviders.FoamCutBaseViewProvider):    
    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        for child in self.Object.Group:
            utilities.setPickStyle(child.ViewObject, utilities.UNPICKABLE)

    def getIcon(self):
        return utilities.getIconPath("origin.svg")
    
    def claimChildren(self):
        return self.Object.Group
    
'''
    Creates Origin
    @param obj - Origin object
    @param config - config object name
'''
def CreateOrigin(obj, jobName):
    MachineOrigin(obj, jobName)
    MachineOriginVP(obj.ViewObject)
    Gui.Selection.clearSelection()