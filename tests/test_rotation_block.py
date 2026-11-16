# -*- coding: utf-8 -*-
"""Rotation foam block tests.

A Rotation shows the Job foam block rotated around the machine rotation axis,
the same way the stock is rotated on the table. The geometry must match the part
rotation, and the block is skipped when the accumulated rotation is a full turn.

Run via FreeCADCmd.exe tests/test_rotation_block.py
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
import Rotate
import utilities
from test_route_postprocess import new_document


BLOCK_POSITION = App.Vector(-50.0, 100.0, 10.0)
BLOCK_SIZE = (100.0, 80.0, 40.0)
ROTATION_ORIGIN = 140.0


def blockVertices(angle):
    '''Reference block rotated by FreeCAD, as a sorted list of rounded points.'''
    box = Part.makeBox(BLOCK_SIZE[0], BLOCK_SIZE[1], BLOCK_SIZE[2], BLOCK_POSITION)
    if angle:
        box.rotate(App.Vector(0.0, ROTATION_ORIGIN, 0.0), App.Vector(0.0, 0.0, 1.0), angle)

    return sorted((round(vertex.Point.x, 5), round(vertex.Point.y, 5), round(vertex.Point.z, 5))
                  for vertex in box.Vertexes)


def cornerTuples(corners):
    return sorted((round(point.x, 5), round(point.y, 5), round(point.z, 5)) for point in corners)


class TestRotatedBlock(unittest.TestCase):

    def setUp(self):
        self.doc, self.job = new_document()
        self.job.BlockWidth = BLOCK_SIZE[0]
        self.job.BlockLength = BLOCK_SIZE[1]
        self.job.BlockHeight = BLOCK_SIZE[2]
        self.job.BlockPosition = BLOCK_POSITION
        self.job.OriginRotationX = ROTATION_ORIGIN
        self.job.FiveAxisMachine = True
        self.doc.recompute()

        self.source = self.doc.addObject("Part::Feature", "Source")
        self.source.Shape = Part.makeBox(20.0, 20.0, 20.0, App.Vector(-10.0, 130.0, 20.0))
        self.doc.recompute()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def makeRotation(self, source, angle):
        rotation = Rotate.createRotation(self.job, source, recompute = False)
        rotation.Angle = angle
        self.doc.recompute()
        return rotation

    def test_block_matches_the_rotated_part(self):
        for angle in (90.0, 45.0, -30.0):
            with self.subTest(angle = angle):
                rotation = self.makeRotation(self.source, angle)
                corners = rotation.Proxy.getRotatedBlockCorners(rotation)
                self.assertIsNotNone(corners)
                self.assertEqual(cornerTuples(corners), blockVertices(angle))

    def test_full_turn_block_matches_the_job_block(self):
        # - A full turn still draws, it just lands on the Job block.
        rotation = self.makeRotation(self.source, 360.0)
        corners = rotation.Proxy.getRotatedBlockCorners(rotation)
        self.assertIsNotNone(corners)
        self.assertEqual(cornerTuples(corners), blockVertices(0.0))

    def test_rotation_chain_accumulates(self):
        first = self.makeRotation(self.source, 90.0)
        second = self.makeRotation(first, -90.0)

        self.assertEqual(first.Proxy.getCumulativeAngle(first), 90.0)
        self.assertEqual(second.Proxy.getCumulativeAngle(second), 0.0)
        # - The second rotation adds up to a full turn, so its block is the Job one.
        self.assertEqual(cornerTuples(second.Proxy.getRotatedBlockCorners(second)), blockVertices(0.0))

    def test_block_outside_machine_is_reported(self):
        rotation = self.makeRotation(self.source, 90.0)
        self.assertEqual(rotation.Proxy.getBlockIssues(rotation), [])

        # - Axis at Y 0: the block swings around it and leaves the travel.
        self.job.OriginRotationX = 0.0
        self.doc.recompute()
        far = self.makeRotation(self.source, 90.0)
        self.assertIn("foam block exceeds the horizontal travel (Y)",
                      far.Proxy.getBlockIssues(far))


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity = 2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
