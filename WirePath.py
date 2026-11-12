# -*- coding: utf-8 -*-

__title__ = "Make Path"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Make Path from 2 selected opposite edges."
__usage__ = """Select 2 opposite edges and activate tool."""

import FreeCAD
App=FreeCAD
import FoamCutBase
from utilities import *

class PathSection(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, edge_l, edge_r, jobName):
        super().__init__(obj, jobName)      
        obj.Type = "Path"

        obj.addProperty("App::PropertyLinkSub",     "LeftEdge",             "Edges",    "Left Edge").LeftEdge = edge_l
        obj.addProperty("App::PropertyLinkSub",     "RightEdge",            "Edges",    "Right Edge").RightEdge = edge_r
        
        obj.setEditorMode("CompensationDirection", 3)
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj): 
        job = obj.Document.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            raise Exception("Active Job not found.")

        wp = getWorkingPlanes(job, obj.Document)
        if wp is None:
            return
    
        leftEdge = obj.LeftEdge[0].getSubObject(obj.LeftEdge[1][0])
        rightEdge = obj.RightEdge[0].getSubObject(obj.RightEdge[1][0])
        
        self.createShape(obj, [leftEdge, rightEdge], wp, (0, 0, 0))


def createPath(job, left_edge, right_edge, label = None, recompute = True):
    '''
    Create a Path object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param left_edge - LinkSub (object, subelement) of the left edge
    @param right_edge - LinkSub (object, subelement) of the right edge
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Path object
    '''
    doc = job.Document
    path = job.newObject("Part::FeaturePython", "Path")
    try:
        PathSection(path, left_edge, right_edge, job.Name)
        if label:
            path.Label = label
    except Exception:
        doc.removeObject(path.Name)
        raise

    if recompute:
        doc.recompute()
    return path


def __getattr__(name):
    # - Old documents stored the view provider as WirePath.PathSectionVP.
    if name == "PathSectionVP":
        from PathGui import PathSectionVP
        return PathSectionVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
