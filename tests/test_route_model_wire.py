# -*- coding: utf-8 -*-
"""Route wire visualization tests.

The route is drawn on the working planes. The optional model wire view projects
the same wire points onto the planes at the original edges, so the wire position
relative to the part can be checked before cutting.

Run via FreeCADCmd.exe tests/test_route_model_wire.py
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import Part
import WirePath
import WireProjection
import WireRoute
from test_route_postprocess import new_document


LEFT_EDGE = (App.Vector(-100.0, 200.0, 100.0), App.Vector(-100.0, 210.0, 100.0))
RIGHT_EDGE = (App.Vector(100.0, 200.0, 120.0), App.Vector(100.0, 210.0, 120.0))


class TestWirePointsAtModel(unittest.TestCase):

    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()

        model = self.doc.addObject("Part::Feature", "Model")
        model.Shape = Part.makeCompound([
            Part.makeLine(LEFT_EDGE[0], LEFT_EDGE[1]),
            Part.makeLine(RIGHT_EDGE[0], RIGHT_EDGE[1]),
        ])
        self.doc.recompute()

        path = WirePath.createPath(
            self.job, (model, "Edge1"), (model, "Edge2"), recompute = False)
        self.doc.recompute()
        self.path = path

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_wire_points_are_projected_to_the_model_planes(self):
        self.job.KerfCompensation = 0.0
        route = WireRoute.createRoute(self.job, [self.path], recompute = True)

        # - One segment, its planes are the X extents of the source edges.
        self.assertEqual(list(route.SegmentLeftPlaneX), [-100.0])
        self.assertEqual(list(route.SegmentRightPlaneX), [100.0])

        (leftGroups, rightGroups) = WireRoute.getWirePointsAtModel(route)
        self.assertEqual(len(leftGroups), 1)
        self.assertEqual(len(rightGroups), 1)
        self.assertEqual(len(leftGroups[0]), len(route.Offset_L))
        self.assertEqual(len(rightGroups[0]), len(route.Offset_L))

        # - Projected wire must pass through the source edges: the route is built
        #   from those edges, so the wire crosses them exactly.
        for point in leftGroups[0]:
            self.assertAlmostEqual(point.x, LEFT_EDGE[0].x, places = 6)
        for point in rightGroups[0]:
            self.assertAlmostEqual(point.x, RIGHT_EDGE[0].x, places = 6)

        self.assertAlmostEqual(leftGroups[0][0].y, LEFT_EDGE[0].y, places = 6)
        self.assertAlmostEqual(leftGroups[0][0].z, LEFT_EDGE[0].z, places = 6)
        self.assertAlmostEqual(leftGroups[0][-1].y, LEFT_EDGE[1].y, places = 6)
        self.assertAlmostEqual(leftGroups[0][-1].z, LEFT_EDGE[1].z, places = 6)

        self.assertAlmostEqual(rightGroups[0][0].y, RIGHT_EDGE[0].y, places = 6)
        self.assertAlmostEqual(rightGroups[0][0].z, RIGHT_EDGE[0].z, places = 6)
        self.assertAlmostEqual(rightGroups[0][-1].y, RIGHT_EDGE[1].y, places = 6)
        self.assertAlmostEqual(rightGroups[0][-1].z, RIGHT_EDGE[1].z, places = 6)

    def test_projection_segment_is_drawn_at_its_source(self):
        # - A projection keeps a single source edge at the model, so its segment
        #   has to be drawn there instead of on the working planes.
        source = Part.makeLine(App.Vector(50.0, 200.0, 100.0), App.Vector(50.0, 210.0, 130.0))
        edge = self.doc.addObject("Part::Feature", "ProjectionSource")
        edge.Shape = source
        self.doc.recompute()

        projection = WireProjection.createProjection(self.job, (edge, "Edge1"), recompute = False)
        self.doc.recompute()

        self.job.KerfCompensation = 0.0
        route = WireRoute.createRoute(self.job, [projection], recompute = True)

        self.assertEqual(list(route.SegmentLeftPlaneX), [50.0])
        self.assertEqual(list(route.SegmentRightPlaneX), [50.0])

        (leftGroups, rightGroups) = WireRoute.getWirePointsAtModel(route)
        self.assertEqual(len(leftGroups), 1)
        self.assertEqual(len(rightGroups), 0)
        self.assertEqual(len(leftGroups[0]), len(route.Offset_L))

        for point in leftGroups[0]:
            self.assertAlmostEqual(point.x, 50.0, places = 6)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity = 2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
