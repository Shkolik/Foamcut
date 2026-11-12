# -*- coding: utf-8 -*-

__title__ = "Join 2 points with path"
__author__ = "Andrew Shkolik & Andrei Bezborodov LGPL"
__license__ = "LGPL 2.1"
__doc__ = "Join 2 selected points with path."
__usage__ = """Select two points on left or right plane and activate tool."""

import FreeCAD
App=FreeCAD
import Part
import FoamCutBase
from utilities import isCommonPoint, isMovement

class WireJoin(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, start, end, jobName):  
        super().__init__(obj, jobName)  
        obj.Type = "Join"
        obj.addProperty("App::PropertyLength",    "FieldWidth","","",5)

        # - Options
        obj.addProperty("App::PropertySpeed",     "FeedRate",  "Options",  "Feed rate" )
        obj.addProperty("App::PropertyInteger",   "WirePower", "Options",  "Wire power")

        obj.addProperty("App::PropertyLinkSub",      "StartPoint",      "Task",   "Start Point").StartPoint = start
        obj.addProperty("App::PropertyLinkSub",      "EndPoint",        "Task",   "End Point").EndPoint = end

        config = self.getConfigName(obj)
        obj.setExpression(".FeedRate", u"<<{}>>.FeedRateCut".format(config))
        obj.setExpression(".WirePower", u"<<{}>>.WireMinPower".format(config))
        obj.setExpression(".FieldWidth", u"<<{}>>.FieldWidth".format(config))
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
        start_vertex = obj.StartPoint[0].getSubObject(obj.StartPoint[1][0])
        if start_vertex is None:
            raise Exception("Unable to locate start point vertex.")

        end_vertex = obj.EndPoint[0].getSubObject(obj.EndPoint[1][0])
        if end_vertex is None:
            raise Exception("Unable to locate end point vertex.")

        (isLeftA, vertexA, oppositeVertexA, wp) = self.findOppositeVertexes(obj, obj.StartPoint[0], start_vertex)
        (isLeftB, vertexB, oppositeVertexB, wp) = self.findOppositeVertexes(obj, obj.EndPoint[0], end_vertex)

        if oppositeVertexA is None:
            raise Exception("Unable to locate opposite vertex for the start point.")

        if oppositeVertexB is None:
            raise Exception("Unable to locate opposite vertex for the end point.")

        if isLeftA != isLeftB:
            raise Exception("Start and End points should be on one side.")

        edges = []

        if isCommonPoint(vertexA, oppositeVertexA):
            edges.append(Part.makeLine(vertexA.Point, vertexB.Point))
        else:
            edges.append(Part.makeLine(vertexA.Point, vertexB.Point))
            edges.append(Part.makeLine(oppositeVertexA.Point, oppositeVertexB.Point))
        
        self.createShape(obj, edges, wp, (35, 0, 205))


def createJoin(job, start, end, label = None, recompute = True):
    '''
    Create a Join object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param start - LinkSub (object, subelement) of the start point
    @param end - LinkSub (object, subelement) of the end point
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Join object
    '''
    doc = job.Document
    join = job.newObject("Part::FeaturePython", "Join")
    try:
        WireJoin(join, start, end, job.Name)
        if label:
            join.Label = label
    except Exception:
        doc.removeObject(join.Name)
        raise

    if recompute:
        doc.recompute()
    return join


def __getattr__(name):
    # - Old documents stored the view provider as WireJoin.WireJoinVP.
    if name == "WireJoinVP":
        from JoinGui import WireJoinVP
        return WireJoinVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
