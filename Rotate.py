# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Rotate selected body."
__usage__ = """Select target body to rotate and activate tool."""

import FreeCAD
App=FreeCAD
import FoamCutBase
from utilities import getJob, jobExpression, bindJob
 
class Rotation(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, source, jobName): 
        super().__init__(obj, jobName)       
        obj.Type = "Rotation"  

        obj.addProperty("App::PropertyDistance",   "OriginRotationX", "", "", 5)

        obj.addProperty("App::PropertyLink",      "Source",     "Task",     "Source object").Source = source
        obj.addProperty("App::PropertyAngle",     "Angle",      "Task",     "Rotate object by angle").Angle = 90
        

        job = getJob(obj)
        bindJob(obj, job)
        obj.setExpression(".OriginRotationX", jobExpression(job, "OriginRotationX"))
        
        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
        if obj.Source is None:
            return

        # - Copy and rotate object
        shape = obj.Source.Shape.copy()
        shape.rotate(App.Vector(0.0, obj.OriginRotationX, 0.0), App.Vector(0,0,1), obj.Angle)
        
        # - Assign new shape
        obj.Shape     = shape
        obj.Placement = shape.Placement


def createRotation(job, source, label = None, recompute = True):
    '''
    Create a Rotation object inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param source - object to rotate
    @param label (optional) - object label
    @param recompute (optional) - recompute the document after creation. True by default
    @returns Rotation object
    '''
    doc = job.Document
    rotation = job.newObject("Part::FeaturePython", "Rotation")
    try:
        Rotation(rotation, source, job.Name)
        if label:
            rotation.Label = label
    except Exception:
        doc.removeObject(rotation.Name)
        raise

    if recompute:
        doc.recompute()
    return rotation


def __getattr__(name):
    # - Old documents stored the view provider as Rotate.RotationVP.
    if name == "RotationVP":
        from RotationGui import RotationVP
        return RotationVP
    raise AttributeError("module {!r} has no attribute {!r}".format(__name__, name))
