# -*- coding: utf-8 -*-

__title__ = "Create Enter path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Enter path to selected point."
__usage__ = """Select point on left or right working plane and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutViewProviders
import FoamCutBase
from utilities import *


class WireEnter(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, entry, jobName):       
        super().__init__(obj, jobName)      
               
        obj.Type = "Enter"

        obj.addProperty("App::PropertyLinkSub",     "EntryPoint",       "Task",     "Entry Point").EntryPoint = entry

        obj.addProperty("App::PropertyDistance",    "SafeHeight",       "Task",     "Safe height" ) 
        obj.addProperty("App::PropertyBool",        "LeadInEnabled",    "Task",     "Add Lead-In").LeadInEnabled = True
        obj.addProperty("App::PropertyDistance",    "LeadInX",          "Task",     "Move along X machine axis" ).LeadInX = 100
        obj.addProperty("App::PropertyDistance",    "LeadInY",          "Task",     "Move along Y machine axis" ).LeadInY = 0

        obj.addProperty("App::PropertyVector",      "EntryPointL",       "", "", 5)
        obj.addProperty("App::PropertyVector",      "EntryPointR",       "", "", 5)

        

        config = self.getConfigName(obj)
        obj.setExpression(".SafeHeight", u"<<{}>>.SafeHeight".format(config))
        
        obj.setEditorMode("LeadInX", 0 if obj.LeadInEnabled else 3)     
        obj.setEditorMode("LeadInY", 0 if obj.LeadInEnabled else 3)     

        obj.Proxy = self
        self.execute(obj)

    def onDocumentRestored(self, obj):
        touched = False
        if not hasattr(obj, "LeadInEnabled"):
            obj.addProperty("App::PropertyBool",        "LeadInEnabled",    "Task",     "Add Lead-In").LeadInEnabled = False   
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadInEnabled property.".format(obj.Label))  
            touched = True
        if not hasattr(obj, "LeadInX"):
            obj.addProperty("App::PropertyDistance",    "LeadInX",          "Task",     "Move along X machine axis" ).LeadInX = 100
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadInX property.".format(obj.Label))  
            touched = True
        if not hasattr(obj, "LeadInY"):
            obj.addProperty("App::PropertyDistance",    "LeadInY",          "Task",     "Move along Y machine axis" ).LeadInY = 0
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadInY property.".format(obj.Label))  
            touched = True  
        if not hasattr(obj, "EntryPointL"):
            obj.addProperty("App::PropertyVector",      "EntryPointL",       "", "", 5)
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding EntryPointL property.".format(obj.Label))  
            touched = True       
        if not hasattr(obj, "EntryPointR"):
            obj.addProperty("App::PropertyVector",      "EntryPointR",       "", "", 5)
            print("{} - Migrating from 0.1.10 to 0.1.11 - adding EntryPointR property.".format(obj.Label))  
            touched = True       

        if touched:
            obj.recompute()

    def onChanged(self, obj, prop):
        super().onChanged(obj, prop)

        if prop == "LeadInEnabled":
            obj.setEditorMode("LeadInX", 0 if obj.LeadInEnabled else 3)     
            obj.setEditorMode("LeadInY", 0 if obj.LeadInEnabled else 3)

    def execute(self, obj):  
        try:
            if obj.SafeHeight > 0:
                # parent object of entry point should be one of FoanCutMovementBaseObject, 
                # otherwise we can't determine opposite vertex and working plane
                nextObj : FoamCutBase.FoamCutMovementBaseObject = obj.EntryPoint[0]

                entryVertex = nextObj.getSubObject(obj.EntryPoint[1][0])
                (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj, nextObj, entryVertex)

                if oppositeVertex is None:
                    raise Exception(f"ERROR: Unable to locate opposite vertex.\n")

                edges = []

                if isCommonPoint(vertex, oppositeVertex):
                    entry = vertex.Point
                    obj.EntryPointL = obj.EntryPointR = entry

                    if obj.LeadInEnabled:
                        entry = App.Vector(vertex.X, vertex.Y + float(obj.LeadInX), vertex.Z + float(obj.LeadInY))
                        edges.append(Part.makeLine(entry, vertex.Point))
                        obj.EntryPointL = obj.EntryPointR = entry
                    else:
                        edges.append(Part.Vertex(entry))
                else:
                    entry = vertex.Point
                    entryOpposite = oppositeVertex.Point
                    if not isLeft:
                        entry = oppositeVertex.Point
                        entryOpposite = vertex.Point

                    obj.EntryPointL = entry
                    obj.EntryPointR = entryOpposite

                    # - if lead-in enabled, calculate lead-in point and add line to entry point
                    if obj.LeadInEnabled:
                        leftLen = getParallelEdgeLength(nextObj, entry.x)
                        rightLen = getParallelEdgeLength(nextObj, entryOpposite.x)
        
                        # Determine nominal (long) side
                        leftIsNominal = leftLen >= rightLen

                        # Avoid division by zero
                        if leftLen > 0 and rightLen > 0:
                            leftScale  = 1.0 if leftIsNominal else leftLen / rightLen
                            rightScale = 1.0 if not leftIsNominal else rightLen / leftLen                        
                        else:
                            leftScale = rightScale = 1.0

                        entryLead = entry + App.Vector(0.0, float(obj.LeadInX) * leftScale, float(obj.LeadInY) * leftScale)
                        oppLead   = entryOpposite + App.Vector(0.0, float(obj.LeadInX) * rightScale, float(obj.LeadInY) * rightScale)

                        edges.append(Part.makeLine(entryLead, entry))
                        edges.append(Part.makeLine(oppLead, entryOpposite))

                        obj.EntryPointL = entryLead
                        obj.EntryPointR = oppLead
                    else:
                        # - enter pathes from safeHeight to the entry point
                        edges.append(Part.Vertex(entry))
                        edges.append(Part.Vertex(entryOpposite))
                    
                self.createShape(obj, edges, wp, (0, 255, 0))
        except Exception as e:
            FreeCAD.Console.PrintError(f"Enter {obj.Label} {e}\n")
            raise

    def getAdditionalShapes(self, obj):
        '''
        return plunge down line from safe height to lead-in end if lead-in enabled or entry point if not
        '''
        shapes = []

        if obj.SafeHeight > 0:
            if obj.EntryPointL == obj.EntryPointR:
                shapes.append(Part.makeLine(App.Vector(obj.EntryPointL.x, obj.EntryPointL.y, obj.SafeHeight), obj.EntryPointL))
            else:
                for p in (obj.EntryPointL, obj.EntryPointR):
                    shapes.append(Part.makeLine(App.Vector(p.x, p.y, obj.SafeHeight), p))
            
            pL = obj.Path_L[START]
            pR = obj.Path_R[START]

            shapes.append(
                Part.makeLine(App.Vector(pL.x, pL.y, obj.SafeHeight),pL)
            )
            
            shapes.append(
                Part.makeLine(App.Vector(pR.x, pR.y, obj.SafeHeight),pR)
            )
        return shapes

class WireEnterVP(FoamCutViewProviders.FoamCutMovementViewProvider):
    def getIcon(self):
        return getIconPath("enter.svg")
    
    def claimChildren(self):
        return [self.Object.EntryPoint[0]] if self.Object.EntryPoint is not None and len(self.Object.EntryPoint) > 0 else None


class MakeEnter():
    """Make Enter"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("enter.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create enter",
                "ToolTip" : "Create enter path object to selected entry point"}

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
            
            enter = None
            try:
                # - Create object
                enter = doc.addObject("Part::FeaturePython", "Enter")
                WireEnter(enter, objects[0], group.Name)
                WireEnterVP(enter.ViewObject)
                enter.ViewObject.PointSize = 4

                group.addObject(enter)

                Gui.Selection.clearSelection()
                Gui.Selection.addSelection(doc.Name, enter.Name)
                
                doc.recompute()
            except Exception as e:                
                FreeCAD.Console.PrintError(f"Failed to create entry.\n")
                if enter is not None:
                    doc.removeObject(enter.Name)    
    
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
            
Gui.addCommand("MakeEnter", MakeEnter())
