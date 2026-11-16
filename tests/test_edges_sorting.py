# -*- coding: utf-8 -*-
"""Edge sorting tests for face based path creation.

When several paths are created at once from two faces, the right edges must be
paired with the left edges they are actually connected to. Distance based
matching is ambiguous when the profiles are offset or rotated, which used to
break the chain of paths.

The sorting itself is domain code and must work without the GUI, so the tests
call it directly from utilities.

Run via FreeCADCmd.exe tests/test_edges_sorting.py
"""

import math
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
import utilities
import WirePath
import WireRoute
from test_route_postprocess import new_document


EXPECTED_PAIRS = [
    ("Edge1", "Edge3"),
    ("Edge5", "Edge7"),
    ("Edge8", "Edge10"),
    ("Edge11", "Edge13"),
    ("Edge14", "Edge16"),
    ("Edge17", "Edge18"),
]


def makeRing(x, centerY, centerZ, radius, count, phase):
    '''Closed polygon wire in the YZ plane.'''
    points = []
    for i in range(count):
        angle = phase + 2.0 * math.pi * i / count
        points.append(App.Vector(x, centerY + radius * math.cos(angle),
                                 centerZ + radius * math.sin(angle)))
    points.append(points[0])
    return Part.makePolygon(points)


def makeLoft(count = 6, phase = math.pi / 6.0):
    '''Loft between a profile and the same profile rotated, so nearest edge is not the opposite one.'''
    left = makeRing(-300.0, 200.0, 100.0, 20.0, count, 0.0)
    right = makeRing(300.0, 206.0, 104.0, 20.0, count, phase)
    return Part.makeLoft([left, right], True)


def endFaces(shape):
    '''Return the two profile faces ordered from left to right.'''
    faces = [face for face in shape.Faces if abs(abs(face.normalAt(0, 0).x) - 1.0) < 1e-6]
    faces.sort(key = lambda face: face.CenterOfMass.x)
    return faces


class EdgeSortingBase(unittest.TestCase):

    def setUp(self):
        self.doc = App.newDocument("EdgeSorting")
        self.shape = makeLoft()
        self.model = self.doc.addObject("Part::Feature", "Model")
        self.model.Shape = self.shape
        self.doc.recompute()

        faces = endFaces(self.model.Shape)
        self.assertEqual(len(faces), 2)
        self.assertEqual(len(faces[0].Edges), 6)

        self.edges_l = list(faces[0].Edges)
        self.edges_r = list(faces[1].Edges)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def edgeName(self, edge):
        index = utilities.findEdgeIndex(self.model.Shape, edge)
        return "Edge{}".format(index)

    def linkNames(self, pairs):
        return [(pair[0][1][0], pair[1][1][0]) for pair in pairs]


class TestFindEdgeIndex(EdgeSortingBase):

    def test_finds_all_face_edges(self):
        indexes = [utilities.findEdgeIndex(self.model.Shape, edge) for edge in self.edges_l]
        self.assertNotIn(None, indexes)
        self.assertEqual(len(set(indexes)), len(indexes))

    def test_finds_reversed_edge(self):
        edge = Part.Edge(self.model.Shape.Edges[0])
        edge.reverse()
        self.assertIsNotNone(utilities.findEdgeIndex(self.model.Shape, edge))

    def test_returns_none_for_foreign_edge(self):
        self.assertIsNone(utilities.findEdgeIndex(self.model.Shape, Part.makeLine(
            App.Vector(0, 0, 0), App.Vector(1, 1, 1))))


class TestSortEdgesByFaces(EdgeSortingBase):

    def test_each_pair_shares_a_connecting_face(self):
        sortedEdges = utilities.sortEdgesByFaces(self.model, self.edges_l, self.edges_r)
        self.assertIsNotNone(sortedEdges)
        self.assertEqual(len(sortedEdges), len(self.edges_l))

        shape = self.model.Shape
        for leftEdge, rightEdge in zip(self.edges_l, sortedEdges):
            leftIndex = utilities.findEdgeIndex(shape, leftEdge)
            rightIndex = utilities.findEdgeIndex(shape, rightEdge)
            self.assertNotEqual(leftIndex, rightIndex)

            sharesFace = False
            for face in shape.Faces:
                faceIndexes = [utilities.findEdgeIndex(shape, edge) for edge in face.Edges]
                if leftIndex in faceIndexes and rightIndex in faceIndexes:
                    sharesFace = True
                    break
            self.assertTrue(sharesFace, "edges {} and {} do not share a face".format(leftIndex, rightIndex))

    def test_pairs_edges_in_profile_order(self):
        sortedEdges = utilities.sortEdgesByFaces(self.model, self.edges_l, self.edges_r)
        pairs = [(self.edgeName(left), self.edgeName(right))
                 for left, right in zip(self.edges_l, sortedEdges)]

        self.assertEqual(pairs, EXPECTED_PAIRS)

    def test_returns_none_without_connecting_faces(self):
        faces = endFaces(self.model.Shape)
        compound = self.doc.addObject("Part::Feature", "DisjointFaces")
        compound.Shape = Part.makeCompound(faces)
        self.doc.recompute()

        self.assertIsNone(utilities.sortEdgesByFaces(
            compound, list(faces[0].Edges), list(faces[1].Edges)))


class TestSortEdges(EdgeSortingBase):

    def test_uses_topology_when_profiles_are_rotated(self):
        pairs = utilities.sortEdges(self.model, self.model, self.edges_l, self.edges_r)
        self.assertEqual(self.linkNames(pairs), EXPECTED_PAIRS)

    def test_single_edge_pair_is_preserved(self):
        pairs = utilities.sortEdges(self.model, self.model, [self.edges_l[0]], [self.edges_r[2]])
        self.assertEqual(len(pairs), 1)

    def test_falls_back_for_disjoint_solids_of_one_object(self):
        # - Two solids in one compound: the profile faces share no connecting
        #   face, so the topology can not pair them and the distance based
        #   pairing is used instead.
        first = Part.makeBox(20.0, 20.0, 20.0)
        second = Part.makeBox(20.0, 20.0, 20.0, App.Vector(60.0, 0.0, 0.0))
        compound = self.doc.addObject("Part::Feature", "TwoSolids")
        compound.Shape = Part.makeCompound([first, second])
        self.doc.recompute()

        faces = [face for face in compound.Shape.Faces
                 if abs(abs(face.normalAt(0, 0).x) - 1.0) < 1e-6]
        faces.sort(key = lambda face: face.CenterOfMass.x)
        edges_l = list(faces[0].Edges)
        edges_r = list(faces[-1].Edges)

        self.assertIsNone(utilities.sortEdgesByFaces(compound, edges_l, edges_r))

        pairs = utilities.sortEdges(compound, compound, edges_l, edges_r)
        self.assertEqual(len(pairs), len(edges_l))

    def test_falls_back_for_faces_of_different_objects(self):
        faces = endFaces(self.model.Shape)

        leftObject = self.doc.addObject("Part::Feature", "LeftFace")
        leftObject.Shape = Part.makeCompound([faces[0]])
        rightObject = self.doc.addObject("Part::Feature", "RightFace")
        rightObject.Shape = Part.makeCompound([faces[1]])
        self.doc.recompute()

        pairs = utilities.sortEdges(
            leftObject, rightObject, list(leftObject.Shape.Edges), list(rightObject.Shape.Edges))
        self.assertEqual(len(pairs), len(faces[0].Edges))


class TestPathChainFromFaces(unittest.TestCase):
    '''Paths created from two faces must share their projected ends.'''

    def setUp(self):
        self.doc, self.job = new_document()
        self.doc.recompute()

        self.model = self.doc.addObject("Part::Feature", "Model")
        self.model.Shape = makeLoft()
        self.doc.recompute()

        faces = endFaces(self.model.Shape)
        self.edges_l = list(faces[0].Edges)
        self.edges_r = list(faces[1].Edges)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_paths_share_their_ends(self):
        pairs = utilities.sortEdges(self.model, self.model, self.edges_l, self.edges_r)
        self.assertEqual(len(pairs), 6)

        paths = []
        for pair in pairs:
            paths.append(WirePath.createPath(
                self.job, (pair[0][0], pair[0][1][0]), (pair[1][0], pair[1][1][0]),
                recompute = False))
        self.doc.recompute()

        # - Consecutive paths come from neighbouring edges of the same profiles,
        #   so their projected ends must coincide.
        for index in range(len(paths)):
            current = paths[index]
            following = paths[(index + 1) % len(paths)]
            distance = current.Path_L[-1].distanceToPoint(following.Path_L[0])
            self.assertLess(distance, 1e-3,
                            "{} and {} are not connected".format(current.Label, following.Label))

        self.job.KerfCompensation = 0.0
        route = WireRoute.createRoute(self.job, paths, recompute = True)
        self.assertGreater(len(route.Offset_L), 0)
        self.assertEqual(len(route.Offset_L), len(route.Offset_R))
        self.assertEqual(list(route.RouteBreaks), [])


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity = 2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
