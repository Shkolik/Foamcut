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

'''
    Returns the current module path.
    Determines where this file is running from, so works regardless of whether
    the module is installed in the app's module directory or the user's app data folder.
    (The second overrides the first.)
'''
def get_module_path():    
    return os.path.dirname(__file__)

def getIconPath(icon):
    return os.path.join(get_module_path(), "Resources", "icons", icon)

def isNewStateHandling():
    return (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]+FreeCAD.Version()[2]) >= '0.212' and (FreeCAD.Version()[0]+'.'+FreeCAD.Version()[1]) < '2000'
    
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
    edge  = Part.makeLine(v0, v1);

    # - Find point of intersection
    point = plane.Shape.Surface.intersect(edge.Curve)[0][0]
    # del edge
    return point



'''
  Get working planes
'''
def getWorkingPlanes():
        doc = FreeCAD.activeDocument()
        # - Initialize result
        result = []
        wpl = doc.getObjectsByLabel('WPL')
        if len(wpl) > 0:
            result.append(wpl[0])
        else:
            print("ERROR: Left working plane not found")
            return None
        wpr = doc.getObjectsByLabel('WPR')
        if len(wpr) > 0:
            result.append(wpr[0])
        else:
            print("ERROR: Right working plane not found")
        
        return result

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