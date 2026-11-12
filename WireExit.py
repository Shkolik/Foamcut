# -*- coding: utf-8 -*-

__title__ = "Create Exit path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Exit path from selected point."
__usage__ = """Select start point on left or right working plane and activate tool."""

import FreeCAD
App=FreeCAD
import Part
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
        if obj.SafeHeight > 0:
            # parent object of entry point should be one of FoanCutMovementBaseObject, 
            # otherwise we can't determine opposite vertex and working plane
            lastObj : FoamCutBase.FoamCutMovementBaseObject = obj.ExitPoint[0]
            
            exitVertex = lastObj.getSubObject(obj.ExitPoint[1][0])
            (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj, lastObj, exitVertex)

            if oppositeVertex is None:
                raise Exception("Unable to locate opposite vertex.")
                
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

    def onDocumentRestored(self, obj):
        super().onDocumentRestored(obj)
        touched = False
        if not hasattr(obj, "LeadOutEnabled"):
            obj.addProperty("App::PropertyBool",        "LeadOutEnabled",    "Task",     "Add Lead-Out").LeadOutEnabled = False   
            App.Console.PrintMessage("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadOutEnabled property.\n".format(obj.Label))  
            touched = True
        if not hasattr(obj, "LeadOutX"):
            obj.addProperty("App::PropertyDistance",    "LeadOutX",          "Task",     "Move along X machine axis" ).LeadOutX = 100
            App.Console.PrintMessage("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadOutX property.\n".format(obj.Label))  
            touched = True
        if not hasattr(obj, "LeadOutY"):
            obj.addProperty("App::PropertyDistance",    "LeadOutY",          "Task",     "Move along Y machine axis" ).LeadOutY = 0
            App.Console.PrintMessage("{} - Migrating from 0.1.10 to 0.1.11 - adding LeadOutY property.\n".format(obj.Label))  
            touched = True  
        if not hasattr(obj, "ExitPointL"):
            obj.addProperty("App::PropertyVector",      "ExitPointL",       "", "", 5)
            App.Console.PrintMessage("{} - Migrating from 0.1.10 to 0.1.11 - adding ExitPointL property.\n".format(obj.Label))  
            touched = True       
        if not hasattr(obj, "ExitPointR"):
            obj.addProperty("App::PropertyVector",      "ExitPointR",       "", "", 5)
            App.Console.PrintMessage("{} - Migrating from 0.1.10 to 0.1.11 - adding ExitPointR property.\n".format(obj.Label))  
            touched = True       

        obj.setEditorMode("LeadOutX", 0 if obj.LeadOutEnabled else 3)     
        obj.setEditorMode("LeadOutY", 0 if obj.LeadOutEnabled else 3)     

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


def createExit(job, exit, label = None, recompute = True):
    '''
    Create an Exit object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param exit - LinkSub (object, subelement) of the exit point
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Exit object
    '''
    doc = job.Document
    exit_object = job.newObject("Part::FeaturePython", "Exit")
    try:
        WireExit(exit_object, exit, job.Name)
        if label:
            exit_object.Label = label
    except Exception:
        doc.removeObject(exit_object.Name)
        raise

    if recompute:
        doc.recompute()
    return exit_object


def __getattr__(name):
    # - Old documents stored the view provider as WireExit.WireExitVP.
    if name == "WireExitVP":
        from ExitGui import WireExitVP
        return WireExitVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
