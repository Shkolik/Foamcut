# -*- coding: utf-8 -*-

__title__ = "Foamcut workbench utilities"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Foamcut workbench utilities common to all tools."

import FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import os

LEFT = -1
RIGHT = 1

'''
    Returns the current module path.
    Determines where this file is running from, so works regardless of whether
    the module is installed in the app's module directory or the user's app data folder.
    (The second overrides the first.)
'''
def get_module_path():    
    return os.path.dirname(__file__)

def getResourcesPath():
    return os.path.join(get_module_path(), "Resources")

def getIconPath(icon):
    return os.path.join(getResourcesPath(), "icons", icon)

def isNewStateHandling():
    return (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]+FreeCAD.Version()[2]) >= '0.212' and (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]) < '2000'

'''
    Converts Part.Vertex to FreeCAD.Vector
    @param v - vertex to convert
    @returns FreeCAD.Vector
'''
def vertexToVector(v):
    return FreeCAD.Vector(v.X, v.Y, v.Z)
      
'''
  Get all selected Edges and Vertexes
'''
def getAllSelectedObjects():
    objects = []
    for obj in  Gui.Selection.getSelectionEx():
        if obj.HasSubObjects:
            i = 0
            for subobj in obj.SubObjects:
                if issubclass(type(subobj), Part.Edge) or issubclass(type(subobj), Part.Vertex):
                    objects.append((obj.Object, [obj.SubElementNames[i]]))
                i += 1
    return objects

'''
  Get all selected Edges
'''
def getAllSelectedEdges():
    objects = []
    for obj in  Gui.Selection.getSelectionEx():
        if obj.HasSubObjects:
            i = 0
            for subobj in obj.SubObjects:
                if issubclass(type(subobj), Part.Edge):
                    objects.append((obj.Object, [obj.SubElementNames[i]]))
                i += 1
    return objects

'''
  Check if points are common
  @param first - Fist point
  @param second - Second point
  @return True if point are common
'''
def isCommonPoint(first, second):
    return True if first.distanceToPoint(second) < 0.01 else False
  
'''
  Find point of intersection of line and plane
  @param v0 - Fist point
  @param v1 - Second point
  @return Point of intersection
'''
def intersectLineAndPlane(v0, v1, plane):
    # - Check is same points and move one of them along X axis to make able to make a line
    if (v0.isEqual(v1, 0.01)):
        v1.x += 1

    # - Make line
    edge  = Part.makeLine(v0, v1)

    # - Find point of intersection
    point = plane.Shape.Surface.intersect(edge.Curve)[0][0]
    # del edge
    return point

'''
    Get Config object by it's name
    @param config - Config object name
    @retuns Config
'''
def getConfigByName(config):
    if config is None or len(config) == 0:
        FreeCAD.Console.PrintError("Error: Config name is empty.\n")
        return
                
    configObj = FreeCAD.ActiveDocument.getObject(config)

    if configObj is None:
        FreeCAD.Console.PrintError("Error: Config not found.\n")
        return
    
    return configObj

'''
  Get working planes
'''
def getWorkingPlanes(group):
        if group is not None and group.Type == "Job":
            # - Initialize result
            result = []
            wpl = FreeCAD.ActiveDocument.getObject(group.WPLName)
            if wpl is not None:
                result.append(wpl)
            else:
                FreeCAD.Console.PrintError("ERROR:\n Left working plane not found.\n")
                return None
            wpr = FreeCAD.ActiveDocument.getObject(group.WPRName)
            if wpr is not None:
                result.append(wpr)
            else:
                FreeCAD.Console.PrintError("ERROR:\n Right working plane not found.\n")
            
            return result
        else:
            FreeCAD.Console.PrintError("ERROR:\n Parent Job not found.\n")

'''
  Enumeration for the pick style
'''
REGULAR = 0
BOUNDBOX = 1
UNPICKABLE = 2

'''
  Get pick style node from view object
  @param viewprovider - view object
  @param create - optional. If set to True node will be added if not found
'''
def getPickStyleNode(viewprovider, create = True):
    from pivy import coin
    sa = coin.SoSearchAction()
    sa.setType(coin.SoPickStyle.getClassTypeId())
    sa.traverse(viewprovider.RootNode)
    if sa.isFound() and sa.getPath().getLength() == 1:
        return sa.getPath().getTail()
    else:
        if not create:
            return None
        node = coin.SoPickStyle()
        node.style.setValue(coin.SoPickStyle.SHAPE)
        viewprovider.RootNode.insertChild(node, 0)
        return node

'''
  Get pick style from view object
  @param viewprovider - view object
'''
def getPickStyle(viewprovider):
    node = getPickStyleNode(viewprovider, create = False)
    if node is not None:
        return node.style.getValue()
    else:
        return REGULAR

'''
  Set pick style
  @param viewprovider - view object
  @param style - pick style. Acceptable values: REGULAR, BOUNDBOX, UNPICKABLE
'''
def setPickStyle(viewprovider, style):
    node = getPickStyleNode(viewprovider, create = style != 0)
    if node is not None:
        return node.style.setValue(style)