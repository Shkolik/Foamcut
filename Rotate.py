# -*- coding: utf-8 -*-

__title__ = "Create Rotation"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Rotate selected body."
__usage__ = """Select target body to rotate and activate tool."""

import FreeCAD
App=FreeCAD
import FoamCutBase
from utilities import getJob, jobExpression, bindJob, getBlockCorners, getBlockOutsideMachine
 
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
        self._ready = False
        self.execute(obj)
        # - The first pass runs before the expressions are evaluated, so the foam
        #   block check waits for the next recompute.
        self._ready = True

    def getCumulativeAngle(self, obj):
        '''
        Get the total rotation angle applied to the source geometry.
        Rotations are chained: a rotation of a rotation adds up, the same way the
        postprocessor emits them.
        @param obj - Rotation object
        @returns accumulated angle in degrees
        '''
        angle = float(obj.Angle)
        source = obj.Source
        visited = {obj.Name}

        while source is not None and getattr(source, "Type", "") == "Rotation":
            if source.Name in visited:
                break
            visited.add(source.Name)
            angle += float(source.Angle)
            source = source.Source

        return angle

    def getRotatedBlockCorners(self, obj):
        '''
        Get the foam block corners rotated with the part on the rotating table.
        The block belongs to the Job; it is rotated around the machine rotation
        axis by the accumulated angle of the rotation chain.
        @param obj - Rotation object
        @returns list of corners or None when the block is not available
        '''
        job = getJob(obj)
        if job is None or not hasattr(job, "BlockWidth"):
            return None

        angle = self.getCumulativeAngle(obj)
        return getBlockCorners(job, float(obj.OriginRotationX), angle)

    def getBlockIssues(self, obj):
        '''
        Check the rotated foam block against the machine travel.
        A block that does not fit the machine can not be cut as placed, so this
        warns before the cut. Visual only: routes are not validated against it.
        @param obj - Rotation object
        @returns list of issues, empty when the block fits
        '''
        corners = self.getRotatedBlockCorners(obj)
        if corners is None:
            return []

        job = getJob(obj)
        return getBlockOutsideMachine(job, corners)

    def reportBlockIssues(self, obj):
        '''
        Print the foam block issues once per state, so a plain recompute does not
        repeat the same warning.
        @param obj - Rotation object
        '''
        if not getattr(self, "_ready", True):
            return

        issues = self.getBlockIssues(obj)
        if issues == getattr(self, "_reportedBlockIssues", None):
            return

        self._reportedBlockIssues = issues
        for issue in issues:
            App.Console.PrintWarning("{}: {}\n".format(obj.Label, issue))

    def execute(self, obj):
        if obj.Source is None:
            return

        # - Copy and rotate object
        shape = obj.Source.Shape.copy()
        shape.rotate(App.Vector(0.0, obj.OriginRotationX, 0.0), App.Vector(0,0,1), obj.Angle)
        
        # - Assign new shape
        obj.Shape     = shape
        obj.Placement = shape.Placement

        self.reportBlockIssues(obj)


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
