# -*- coding: utf-8 -*-

__title__ = "Create Exit path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Exit path from selected point."
__usage__ = """Select start point on left or right working plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutViewProviders
import FoamCutBase
from utilities import *

class WireExit(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, exit, jobName):
        super().__init__(obj, jobName) 
        
        obj.Type = "Exit"
        
        obj.addProperty("App::PropertyDistance",    "SafeHeight",           "Task",     "Safe height")
        obj.addProperty("App::PropertyLinkSub",     "ExitPoint",            "Task",     "Exit Point").ExitPoint = exit

        obj.addProperty("App::PropertyBool",        "LeadOutEnabled",    "Task",     "Add Lead-Out").LeadOutEnabled = True
        obj.addProperty("App::PropertyDistance",    "LeadOutX",          "Task",     "Move along X machine axis" ).LeadOutX = 100
        obj.addProperty("App::PropertyDistance",    "LeadOutY",          "Task",     "Move along Y machine axis" ).LeadOutY = 0

        obj.addProperty("App::PropertyVector",      "ExitPointL",       "", "", 5)
        obj.addProperty("App::PropertyVector",      "ExitPointR",       "", "", 5)

        config = self.getConfigName(obj)
        obj.setExpression(".SafeHeight", u"<<{}>>.SafeHeight".format(config))

        obj.setEditorMode("LeadOutX", 0 if obj.LeadOutEnabled else 3)     
        obj.setEditorMode("LeadOutY", 0 if obj.LeadOutEnabled else 3)     

        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj): 
        try:
            if obj.SafeHeight > 0:
                # parent object of entry point should be one of FoanCutMovementBaseObject, 
                # otherwise we can't determine opposite vertex and working plane
                lastObj : FoamCutBase.FoamCutMovementBaseObject = obj.ExitPoint[0]
                
                exitVertex = lastObj.getSubObject(obj.ExitPoint[1][0])
                (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj, lastObj, exitVertex)

                if oppositeVertex is None:
                    raise Exception(f"ERROR: Unable to locate opposite vertex.\n")
                    
                edges = []

                if isCommonPoint(vertex, oppositeVertex):
                    exit = vertex.Point
                    obj.ExitPointL = obj.ExitPointR = exit
                    if obj.LeadOutEnabled:
                        exit = App.Vector(vertex.X, vertex.Y + float(obj.LeadOutX), vertex.Z + float(obj.LeadOutY))
                        edges.append(Part.makeLine(vertex.Point, exit))
                        obj.ExitPointL = obj.ExitPointR = exit
                    else:
                        edges.append(Part.Vertex(exit))
                else:
                    exit = vertex.Point
                    exitOpposite = oppositeVertex.Point
                    if not isLeft:
                        exit = oppositeVertex.Point
                        exitOpposite = vertex.Point

                    obj.ExitPointL = exit
                    obj.ExitPointR = exitOpposite

                    # - if lead-out enabled, calculate lead-out point and add line to exit point
                    if obj.LeadOutEnabled:
                        leftLen = getParallelEdgeLength(lastObj, exit.x)
                        rightLen = getParallelEdgeLength(lastObj, exitOpposite.x)

                        # Determine nominal (long) side
                        leftIsNominal = leftLen >= rightLen

                        # Avoid division by zero
                        if leftLen > 0 and rightLen > 0:
                            leftScale  = 1.0 if leftIsNominal else leftLen / rightLen
                            rightScale = 1.0 if not leftIsNominal else rightLen / leftLen
                        else:
                            leftScale = rightScale = 1.0

                        exitLead = exit + App.Vector(0.0, float(obj.LeadOutX) * leftScale, float(obj.LeadOutY) * leftScale)
                        oppLead   = exitOpposite + App.Vector(0.0, float(obj.LeadOutX) * rightScale, float(obj.LeadOutY) * rightScale)

                        edges.append(Part.makeLine(exit, exitLead))
                        edges.append(Part.makeLine(exitOpposite, oppLead))
                        obj.ExitPointL = exitLead
                        obj.ExitPointR = oppLead
                    else:
                        # - exit pathes from exit point to safeHeight
                        edges.append(Part.Vertex(exit))
                        edges.append(Part.Vertex(exitOpposite))
                        
                self.createShape(obj, edges, wp, (255, 0, 0))
        except Exception as e:
            FreeCAD.Console.PrintError(f"Exit {obj.Label} {e}\n")
            raise

    def onDocumentRestored(self, obj):
        touched = False
        if not hasattr(obj, "LeadOutEnabled"):
            obj.addProperty("App::PropertyBool",        "LeadOutEnabled",    "Task",     "Add Lead-Out").LeadOutEnabled = False   
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadOutEnabled property.".format(obj.Label))  
            touched = True
        if not hasattr(obj, "LeadOutX"):
            obj.addProperty("App::PropertyDistance",    "LeadOutX",          "Task",     "Move along X machine axis" ).LeadOutX = 100
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadOutX property.".format(obj.Label))  
            touched = True
        if not hasattr(obj, "LeadOutY"):
            obj.addProperty("App::PropertyDistance",    "LeadOutY",          "Task",     "Move along Y machine axis" ).LeadOutY = 0
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadOutY property.".format(obj.Label))  
            touched = True  
        if not hasattr(obj, "ExitPointL"):
            obj.addProperty("App::PropertyVector",      "ExitPointL",       "", "", 5)
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding ExitPointL property.".format(obj.Label))  
            touched = True       
        if not hasattr(obj, "ExitPointR"):
            obj.addProperty("App::PropertyVector",      "ExitPointR",       "", "", 5)
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding ExitPointR property.".format(obj.Label))  
            touched = True       

        if touched:
            obj.recompute()

    def onChanged(self, obj, prop):
        super().onChanged(obj, prop)

        if prop == "LeadOutEnabled":
            obj.setEditorMode("LeadOutX", 0 if obj.LeadOutEnabled else 3)     
            obj.setEditorMode("LeadOutY", 0 if obj.LeadOutEnabled else 3)

    def getAdditionalShapes(self, obj):
        '''
        return plunge up line from lead-out end if lead-out enabled or exit point if not to safe height
        '''
        shapes = []

        if obj.SafeHeight > 0:
            if obj.ExitPointL == obj.ExitPointR:
                shapes.append(Part.makeLine(obj.ExitPointL, App.Vector(obj.ExitPointL.x, obj.ExitPointL.y, obj.SafeHeight)))
            else:
                for p in (obj.ExitPointL, obj.ExitPointR):                    
                    shapes.append(Part.makeLine(p, App.Vector(p.x, p.y, obj.SafeHeight)))
            
            pL = obj.Path_L[END]
            pR = obj.Path_R[END]

            shapes.append(
                Part.makeLine(pL, App.Vector(pL.x, pL.y, obj.SafeHeight))
            )
            
            shapes.append(
                Part.makeLine(pR, App.Vector(pR.x, pR.y, obj.SafeHeight))
            )
        return shapes
    
class WireExitVP(FoamCutViewProviders.FoamCutMovementViewProvider):    
    def getIcon(self):        
        return getIconPath("exit.svg")

    def claimChildren(self):
        return [self.Object.ExitPoint[0]] if self.Object.ExitPoint is not None and len(self.Object.ExitPoint) > 0 else None

class MakeExit():
    """Make Exit"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("exit.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create exit",
                "ToolTip" : "Create exit path object from selected entry point"}

    def Activated(self):
        doc = App.ActiveDocument
        view = Gui.ActiveDocument.ActiveView

        group = view.getActiveObject("group")
        setActive = False
        # - if machine is not active, try to select first one in a document
        if group is None or group.Type != "Job":
            group = doc.getObject("Job")
            setActive = True

        if group is not None and group.Type == "Job":
            if setActive:
                view.setActiveObject("group", group)
            
            # - Get selecttion
            objects = getAllSelectedObjects()
            
            exit = None
            try:
                # - Create object
                exit = doc.addObject("Part::FeaturePython", "Exit")
                WireExit(exit, objects[0], group.Name)
                WireExitVP(exit.ViewObject)
                exit.ViewObject.PointSize = 4
                
                group.addObject(exit)

                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(doc.Name, exit.Name)
                
                doc.recompute()
            except Exception as e:
                FreeCAD.Console.PrintError(f"Failed to create exit.\n")
                if exit is not None:
                    doc.removeObject(exit.Name) 

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":
                # - Get selecttion
                objects = getAllSelectedObjects()

                # - nothing selected
                if len(objects) == 0:
                    return False
                
                object = objects[0]
                parent = object[0]
                vertex = parent.getSubObject(object[1][0])
                # - Check object type
                if not issubclass(type(vertex), Part.Vertex):
                    return False
                
                wp = getWorkingPlanes(group, App.ActiveDocument)
                if wp is None or len(wp) != 2:
                    return False
                
                return True
            return False
        
Gui.addCommand("MakeExit", MakeExit())
