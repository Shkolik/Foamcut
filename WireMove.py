# -*- coding: utf-8 -*-

__title__ = "Create Move path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create Move path from selected point."
__usage__ = """Select start point on left or right plane and activate tool."""

import FreeCAD
App=FreeCAD
import Part
import FoamCutBase
from utilities import *

class WireMove(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, start, jobName):     
        super().__init__(obj, jobName)     
        obj.Type = "Move"

        # - Options
        obj.addProperty("App::PropertyDistance",    "MoveX",        "Task",     "Move along X machine axis" ).MoveX = 100
        obj.addProperty("App::PropertyDistance",    "MoveY",        "Task",     "Move along Y machine axis" ).MoveY = 0
        obj.addProperty("App::PropertySpeed",       "FeedRate",     "Task",     "Feed rate")
        obj.addProperty("App::PropertyInteger",     "WirePower",    "Task",     "Wire power")
        obj.addProperty("App::PropertyLinkSub",     "StartPoint",   "Task",     "Start Point").StartPoint = start

        config = self.getConfigName(obj)
        obj.setExpression(".FeedRate", u"<<{}>>.FeedRateCut".format(config))
        obj.setExpression(".WirePower", u"<<{}>>.WireMinPower".format(config))

        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):       
        start_vertex = obj.StartPoint[0].getSubObject(obj.StartPoint[1][0])
        if start_vertex is None:
            raise Exception("Unable to locate start point vertex.")

        (isLeft, vertex, oppositeVertex, wp) = self.findOppositeVertexes(obj, obj.StartPoint[0], start_vertex)
        
        if oppositeVertex is None:
            raise Exception("Unable to locate opposite vertex.")
            
        edges = []

        if isCommonPoint(vertex, oppositeVertex):
            edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertex.Point))
        else:
            edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertex.Point) if isLeft                      \
                else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y + float(obj.MoveX), oppositeVertex.Z + float(obj.MoveY)), oppositeVertex.Point))
            edges.append(Part.makeLine(App.Vector(vertex.X, vertex.Y + float(obj.MoveX), vertex.Z + float(obj.MoveY)), vertex.Point) if not isLeft                  \
                else Part.makeLine(App.Vector(oppositeVertex.X, oppositeVertex.Y + float(obj.MoveX), oppositeVertex.Z + float(obj.MoveY)), oppositeVertex.Point))
        
        self.createShape(obj, edges, wp, (35, 169, 205))


def createMove(job, start, label = None, recompute = True):
    '''
    Create a Move object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param start - LinkSub (object, subelement) of the start point
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Move object
    '''
    doc = job.Document
    move = job.newObject("Part::FeaturePython", "Move")
    try:
        WireMove(move, start, job.Name)
        if label:
            move.Label = label
    except Exception:
        doc.removeObject(move.Name)
        raise

    if recompute:
        doc.recompute()
    return move


def __getattr__(name):
    # - Old documents stored the view provider as WireMove.WireMoveVP.
    if name == "WireMoveVP":
        from MoveGui import WireMoveVP
        return WireMoveVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
