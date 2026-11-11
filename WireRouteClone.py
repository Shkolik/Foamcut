# -*- coding: utf-8 -*-

__title__ = "Duplicate route"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Parametric clone of a route, with relative placement and mirroring."
__usage__ = """Created by the Duplicate route command."""

import FreeCAD
App=FreeCAD
import FoamCutBase
import WireRoute
import utilities

FC_ROUTE_MIRROR_MODES = ["None", "YZ", "XY", "YZ+XY"]


class WireRouteClone(FoamCutBase.FoamCutBaseObject):
    """Route clone: follows the source route; offset and mirror are applied on use."""

    def __init__(self, obj, source, jobName):
        super().__init__(obj, jobName)
        obj.Type = "RouteClone"

        obj.addProperty("App::PropertyLink",         "Source",   "Task", "Source route. The clone follows its changes.")
        obj.addProperty("App::PropertyVector",       "Position", "Task",
                        "Offset relative to the source route along machine Y (length) and Z (height). X is ignored.")
        obj.addProperty("App::PropertyEnumeration",  "Mirror",   "Task",
                        "Mirror the route: YZ mirrors horizontally, XY mirrors vertically about block mid-height. Rotation angles are reversed.").Mirror = FC_ROUTE_MIRROR_MODES
        obj.addProperty("App::PropertyInteger",      "Redraw",   "", "", 5).Redraw = 0

        obj.Source = source
        obj.Position = App.Vector(0.0, 0.0, 0.0)
        obj.Mirror = "None"

        obj.Proxy = self
        self.execute(obj)

    def execute(self, obj):
        if obj.Source is None:
            App.Console.PrintWarning("{} - clone has no source route. Select the source or delete the clone.\n".format(obj.Label))
            obj.Redraw += 1
            return

        self.validatePosition(obj, obj.Position, obj.Mirror)
        obj.Redraw += 1

    def onChanged(self, obj, prop):
        # - Keep the 3D view in sync when placement/mirror are edited from the property editor
        if prop not in ("Position", "Mirror", "Source"):
            return

        view_object = getattr(obj, "ViewObject", None)
        proxy = getattr(view_object, "Proxy", None) if view_object is not None else None
        if proxy is None or not hasattr(proxy, "drawRoute"):
            return

        try:
            proxy.drawRoute()
        except Exception:
            pass

    def getSourceRoute(self, obj):
        '''
        Return the route that owns the geometry.
        Raises when the source is missing, is itself a clone, or is not a route.
        '''
        source = obj.Source
        if source is None:
            raise Exception("ERROR: Route clone [{}] has no source route.".format(obj.Label))
        if getattr(source, "Type", None) == "RouteClone":
            raise Exception("ERROR: Route clone [{}] source [{}] is itself a clone; duplicate the original route instead.".format(obj.Label, source.Label))
        if getattr(source, "Type", None) != "Route":
            raise Exception("ERROR: Route clone [{}] source [{}] is not a route. Select an original route.".format(obj.Label, source.Label))
        if getattr(source, "JobName", None) != obj.JobName:
            raise Exception("ERROR: Route clone [{}] source [{}] belongs to another job. Select a route from the same job.".format(obj.Label, source.Label))
        return source

    def getPivotZ(self, obj):
        '''
        Vertical pivot of the XY mirror: the middle of the foam block.
        '''
        job = obj.Document.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            raise Exception("ERROR: Job [{}] not found for XY mirror.".format(obj.JobName))
        config = job.getObject(job.ConfigName)
        if config is None or not hasattr(config, "BlockPosition") or not hasattr(config, "BlockHeight"):
            raise Exception("ERROR: Foam block geometry not found for XY mirror.")
        return float(config.BlockPosition.z) + float(config.BlockHeight) / 2.0

    def transformPoints(self, obj, position, mirror):
        '''
        Apply reflection, placement and plane swap to the source points.
        Order: XY reflection and lead rebuild, translation, YZ swap.
        '''
        source = self.getSourceRoute(obj)
        points_L = list(source.Offset_L)
        points_R = list(source.Offset_R)

        if mirror in ("XY", "YZ+XY") and (points_L or points_R):
            pivot = self.getPivotZ(obj)
            points_L = WireRoute.mirrorRoutePointsXY(source, points_L, pivot)
            points_R = WireRoute.mirrorRoutePointsXY(source, points_R, pivot)

        points_L = [self.applyOffset(point, position) for point in points_L]
        points_R = [self.applyOffset(point, position) for point in points_R]

        if mirror in ("YZ", "YZ+XY"):
            # Swap the profiles but keep every point on its own wire plane
            # (x belongs to the plane, y/z are the swapped geometry)
            points_L, points_R = (
                [App.Vector(left.x, right.y, right.z) for left, right in zip(points_L, points_R)],
                [App.Vector(right.x, left.y, left.z) for left, right in zip(points_L, points_R)],
            )

        return (points_L, points_R)

    @staticmethod
    def applyOffset(point, position):
        if abs(position.y) < 1e-12 and abs(position.z) < 1e-12:
            return point
        return App.Vector(point.x, point.y + float(position.y), point.z + float(position.z))

    def getOutputPoints(self, obj):
        return self.transformPoints(obj, obj.Position, obj.Mirror)

    def getRotationAngle(self, obj, angle):
        if obj.Mirror != "None":
            return -float(angle)
        return float(angle)

    def validatePosition(self, obj, position, mirror = None):
        '''
        Validate a candidate position/mirror against the working area.
        @returns tuple of transformed points (points_L, points_R)
        Raises when the moved points leave the working area.
        '''
        mirror = obj.Mirror if mirror is None else mirror
        points_L, points_R = self.transformPoints(obj, position, mirror)

        job = obj.Document.getObject(obj.JobName)
        if job is None or job.Type != "Job":
            raise Exception("ERROR: Job [{}] not found.".format(obj.JobName))

        planes = utilities.getWorkingPlanes(job, obj.Document)
        if planes is None or len(planes) != 2:
            raise Exception("ERROR: Working planes not found.")

        utilities.validateWorkingArea(points_L, points_R, planes[0], planes[1])
        return (points_L, points_R)


def setRoutePosition(clone, position, mirror = None):
    '''
    Validate and apply position/mirror to a route clone.
    Raises when the moved route leaves the working area; properties are not changed in that case.
    '''
    clone.Proxy.validatePosition(clone, position, mirror)
    clone.Position = position
    if mirror is not None:
        clone.Mirror = mirror
    doc = getattr(clone, "Document", None)
    if doc is not None:
        doc.recompute()


def canDuplicateRoute(obj):
    '''
    Only an original route can be duplicated.
    '''
    return obj is not None and getattr(obj, "Type", None) == "Route" and getattr(obj, "Source", None) is None


def getJobRoutes(job):
    '''
    Return the original routes of a job, sorted by label.
    @param job - Job group
    '''
    if job is None:
        return []

    routes = []
    for object in job.Group:
        if getattr(object, "Type", None) == "Route" and not getattr(object, "Source", None):
            routes.append(object)
    return sorted(routes, key = lambda route: route.Label)


def validateCloneSource(job, source):
    '''
    Validate that a source can be duplicated into a job.
    @param job - Job group
    @param source - original Route object
    Raises when the job is missing, the source is not an original route,
    or the source belongs to another job.
    '''
    if job is None or getattr(job, "Type", None) != "Job":
        raise Exception("ERROR: Job is not defined.")

    if not canDuplicateRoute(source):
        if source is None:
            raise Exception("ERROR: No source route selected.")
        raise Exception("ERROR: [{}] is not an original route. Only original routes can be duplicated.".format(getattr(source, "Label", source)))

    if getattr(source, "JobName", None) != job.Name:
        raise Exception("ERROR: Route [{}] belongs to another job.".format(source.Label))
    return source


def createRouteClone(job, source, label = None, recompute = True):
    '''
    Create a parametric route clone inside a job.
    Script-friendly entry point: no GUI is required.
    @param job - Job group
    @param source - original Route object
    @param label (optional) - clone label; '{source_label}_clone' by default
    @param recompute (optional) - recompute the document after creation. True by default
    @returns RouteClone object
    '''
    validateCloneSource(job, source)

    doc = job.Document
    clone = job.newObject("App::FeaturePython", "RouteClone")
    try:
        WireRouteClone(clone, source, job.Name)
        clone.Label = label if label else "{}_clone".format(source.Label)
    except Exception:
        doc.removeObject(clone.Name)
        raise

    if recompute:
        doc.recompute()
    return clone
