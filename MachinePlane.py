# -*- coding: utf-8 -*-

__title__ = "Working plane"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Working plane value object derived from Job configuration."

import FreeCAD
App = FreeCAD
import Part
import utilities


class WorkingPlane:
    '''
    Snapshot of one working plane.

    Instances are created fresh by utilities.getWorkingPlanes() for every
    calculation. They are not document objects and have no cache that could
    survive a Job configuration change.
    '''

    def __init__(self, job, side):
        self.Side = side
        self.Type = "WorkingPlane"

        if getattr(job, "WorkingPlaneCustom", False):
            left_x = float(job.WorkingPlaneLeftX)
            right_x = float(job.WorkingPlaneRightX)
            self.Position = App.Vector(left_x if side == utilities.LEFT else right_x,
                                       float(job.WorkingPlaneY), 0.0)
            self.Length = float(job.WorkingPlaneLength)
            self.Width = float(job.WorkingPlaneWidth)
        else:
            x = -float(job.FieldWidth) / 2.0 if side == utilities.LEFT else float(job.FieldWidth) / 2.0
            self.Position = App.Vector(x, -float(job.OriginX), 0.0)
            self.Length = float(job.HorizontalTravel)
            self.Width = float(job.VerticalTravel)

        self.Label = "Working Plane L" if side == utilities.LEFT else "Working Plane R"
        self.Name = "WPL" if side == utilities.LEFT else "WPR"
        self._shape = None
        self._surface = None

    @classmethod
    def fromX(cls, job, x):
        '''
        Build a snapshot plane at an arbitrary machine X position.
        Used by route segment projection; still a fresh value object.
        '''
        plane = cls.__new__(cls)
        plane.Side = None
        plane.Type = "WorkingPlane"
        plane.Position = App.Vector(float(x), -float(job.OriginX), 0.0)
        plane.Length = float(job.HorizontalTravel)
        plane.Width = float(job.VerticalTravel)
        plane.Label = "Working Plane X={}".format(x)
        plane.Name = "WorkingPlane"
        plane._shape = None
        plane._surface = None
        return plane

    @property
    def Shape(self):
        if self._shape is None:
            self._shape = Part.makePlane(
                self.Length,
                self.Width,
                self.Position,
                App.Vector(1.0, 0.0, 0.0),
                App.Vector(0.0, 1.0, 0.0))
        return self._shape

    @property
    def Surface(self):
        if self._surface is None:
            self._surface = self.Shape.Surface
        return self._surface

    def intersectLine(self, v0, v1):
        '''
        Intersect a line with this constant-X plane.
        @returns App.Vector intersection point
        '''
        dx = v1.x - v0.x
        if abs(dx) < 1e-12:
            raise Exception(
                "Line ({}, {}, {}) - ({}, {}, {}) is parallel to the plane; no intersection".format(
                    v0.x, v0.y, v0.z, v1.x, v1.y, v1.z))

        t = (self.Position.x - v0.x) / dx
        return App.Vector(
            self.Position.x,
            v0.y + (v1.y - v0.y) * t,
            v0.z + (v1.z - v0.z) * t)
