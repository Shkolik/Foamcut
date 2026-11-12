# -*- coding: utf-8 -*-

__title__ = "Create Projection"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Create projection from selected face, edge or vertex."
__usage__ = """Select face, edge or vertex and activate tool."""

import FreeCAD
App=FreeCAD
import FoamCutBase
import Part
from utilities import getWorkingPlanes


class ProjectionSection(FoamCutBase.FoamCutMovementBaseObject):
    def __init__(self, obj, source, jobName):
        super().__init__(obj, jobName)
        obj.Type = "Projection"
        obj.addProperty("App::PropertyLinkSub", "Source", "Data", "Source object to project").Source = source

        obj.setEditorMode("CompensationDirection", 3)
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
        job = obj.Document.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            raise Exception("Active Job not found.")

        # - Get working planes
        wp = getWorkingPlanes(job, obj.Document)
        
        if wp is None or len(wp) != 2:
            return

        source = obj.Source[0].getSubObject(obj.Source[1])[0]

        self.createShape(obj, [source], wp, (0, 0, 0))


def createProjection(job, source, label = None, recompute = True):
    '''
    Create a Projection object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param source - LinkSub (object, subelement) of the source geometry
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Projection object
    '''
    doc = job.Document
    projection = job.newObject("Part::FeaturePython", "Projection")
    try:
        ProjectionSection(projection, source, job.Name)
        if label:
            projection.Label = label
    except Exception:
        doc.removeObject(projection.Name)
        raise

    if recompute:
        doc.recompute()
    return projection


def __getattr__(name):
    # - Old documents stored the view provider as WireProjection.ProjectionSectionVP.
    if name == "ProjectionSectionVP":
        from ProjectionGui import ProjectionSectionVP
        return ProjectionSectionVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
