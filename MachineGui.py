# -*- coding: utf-8 -*-

__title__ = "Job GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Job view provider and inline machine graphics."

import math
import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import pivy.coin as coin
import utilities
import FoamCutViewProviders

VIEW_PROPERTIES = (
    ("ShowCNCVolume", "Show CNC volume"),
    ("ShowFoamBlock", "Show foam block"),
    ("ShowWorkingPlanes", "Show working planes"),
    ("ShowOrigin", "Show machine origin"),
    ("ShowRotationAxis", "Show rotation axis"),
)
VIEW_PROPERTY_NAMES = tuple(name for name, _ in VIEW_PROPERTIES)
DRAW_PROPERTIES = (
    "FieldWidth", "HorizontalTravel", "VerticalTravel", "OriginX",
    "OriginRotationX", "BlockWidth", "BlockLength", "BlockHeight",
    "BlockPosition", "FiveAxisMachine",
)


def _line(points, color, width = 1, transparency = 0.0):
    separator = coin.SoSeparator()
    draw_style = coin.SoDrawStyle()
    draw_style.style = coin.SoDrawStyle.LINES
    draw_style.lineWidth = width
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    line = coin.SoLineSet()
    line.numVertices.setValue(len(points))
    separator.addChild(draw_style)
    if transparency > 0.0:
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.transparency.setValue(transparency)
        separator.addChild(material)
    else:
        base_color = coin.SoBaseColor()
        base_color.rgb.setValue(*color)
        separator.addChild(base_color)
    separator.addChild(coords)
    separator.addChild(line)
    return separator


def _face(points, color, transparency = 0.0):
    separator = coin.SoSeparator()
    draw_style = coin.SoDrawStyle()
    draw_style.style = coin.SoDrawStyle.FILLED
    material = coin.SoMaterial()
    material.diffuseColor.setValue(*color)
    material.transparency.setValue(transparency)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, len(points), points)
    face = coin.SoFaceSet()
    face.numVertices.setValue(len(points))
    separator.addChild(draw_style)
    separator.addChild(material)
    separator.addChild(coords)
    separator.addChild(face)
    return separator


def _box_corners(x, y, z, length, width, height):
    x2 = x + length
    y2 = y + width
    z2 = z + height
    return [
        (x, y, z), (x2, y, z), (x2, y2, z), (x, y2, z),
        (x, y, z2), (x2, y, z2), (x2, y2, z2), (x, y2, z2),
    ]


def _box_edges(corners):
    edges = [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ]
    return [[corners[first], corners[second]] for first, second in edges]


def _box_faces(corners):
    return [
        [corners[0], corners[1], corners[2], corners[3]],
        [corners[4], corners[5], corners[6], corners[7]],
        [corners[0], corners[1], corners[5], corners[4]],
        [corners[1], corners[2], corners[6], corners[5]],
        [corners[2], corners[3], corners[7], corners[6]],
        [corners[3], corners[0], corners[4], corners[7]],
    ]


def _box(x, y, z, length, width, height, face_color, transparency, edge_color):
    group = coin.SoSeparator()
    corners = _box_corners(x, y, z, length, width, height)
    for face in _box_faces(corners):
        group.addChild(_face(face, face_color, transparency))
    for edge in _box_edges(corners):
        group.addChild(_line(edge, edge_color, 1))
    return group


def _origin_axis(label, length, rotate, mirror, color):
    '''Origin axis drawing borrowed from the old MachineOrigin view provider.'''
    line = coin.SoLineSet()
    line.numVertices.setValue(2)
    coords = coin.SoCoordinate3()
    coords.point.setValues(0, [[0, 0, 0], [0, length, 0]])

    cone = coin.SoCone()
    cone.bottomRadius = 2.0
    cone.height = 10.0

    font = coin.SoFont()
    font.name = "Arial"
    font.size = 10.0

    text = coin.SoAsciiText()
    text.string = label

    text_transform = coin.SoTransform()
    rotation_x = coin.SbRotation(coin.SbVec3f(1, 0, 0), math.radians(0 if rotate else 90))
    rotation_y = coin.SbRotation(coin.SbVec3f(0, 1, 0), math.radians(270))
    text_transform.rotation.setValue(rotation_y * rotation_x)
    if mirror:
        if rotate:
            text_transform.translation.setValue(0, -5, -5)
        else:
            text_transform.translation.setValue(0, -5, 5)
        text_transform.scaleFactor.setValue(-1, 1, 1)
    else:
        if rotate:
            text_transform.translation.setValue(0, -5, -15)
        else:
            text_transform.translation.setValue(0, 5, 5)
        text_transform.scaleFactor.setValue(1, 1, 1)

    shape_hints = coin.SoShapeHints()
    shape_hints.vertexOrdering = coin.SoShapeHints.CLOCKWISE if mirror else coin.SoShapeHints.COUNTERCLOCKWISE

    cone_transform = coin.SoTransform()
    cone_transform.translation.setValue(0, length, 0)

    rotation_transform = coin.SoTransform()
    rotation_transform.rotation.setValue(coin.SbVec3f(1, 0, 0), math.radians(90 if rotate else 0))

    text_node = coin.SoGroup()
    text_node.addChild(text_transform)
    text_node.addChild(font)
    text_node.addChild(shape_hints)
    text_node.addChild(text)

    axis_node = coin.SoGroup()
    axis_node.addChild(rotation_transform)

    draw_style = coin.SoDrawStyle()
    draw_style.style = coin.SoDrawStyle.FILLED
    draw_style.lineWidth = 3
    base_color = coin.SoBaseColor()
    base_color.rgb.setValue(*color)

    axis_sep = coin.SoSeparator()
    axis_sep.addChild(draw_style)
    axis_sep.addChild(base_color)
    axis_sep.addChild(coords)
    axis_sep.addChild(line)
    axis_sep.addChild(cone_transform)
    axis_sep.addChild(cone)
    axis_sep.addChild(text_node)
    axis_node.addChild(axis_sep)
    return axis_node


def _ensure_view_properties(obj):
    for name, description in VIEW_PROPERTIES:
        if not hasattr(obj, name):
            obj.addProperty("App::PropertyBool", name, "Machine Graphics", description)
            setattr(obj, name, True)


class MachineVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    def __init__(self, obj):
        super().__init__(obj)
        _ensure_view_properties(obj)

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        _ensure_view_properties(obj)

        self.node = coin.SoSeparator()
        self.draw()
        obj.RootNode.addChild(self.node)
        utilities.setPickStyle(obj, utilities.UNPICKABLE)

    def getIcon(self):
        return utilities.getIconPath("machine.svg")

    def doubleClicked(self, obj):
        if Gui.ActiveDocument.ActiveView.getActiveObject("group") == obj.Object:
            Gui.ActiveDocument.ActiveView.setActiveObject("group", None)
        else:
            Gui.ActiveDocument.ActiveView.setActiveObject("group", obj.Object)
        return True

    def updateData(self, obj, prop):
        if hasattr(self, "node") and prop not in ("Group", "Label", "Proxy"):
            self.draw()

    def onChanged(self, obj, prop):
        if hasattr(self, "node") and (prop in VIEW_PROPERTY_NAMES or prop == "Visibility"):
            self.draw()

    def visible(self, name):
        if self.ViewObject is None:
            return True
        return bool(getattr(self.ViewObject, name, True))

    def draw(self):
        while self.node.getNumChildren() > 0:
            self.node.removeChild(0)

        if self.ViewObject is not None and not getattr(self.ViewObject, "Visibility", True):
            return

        job = self.Object
        if not all(hasattr(job, name) for name in DRAW_PROPERTIES):
            return

        try:
            if self.visible("ShowCNCVolume"):
                self.node.addChild(self.drawVolume(job))
            if self.visible("ShowFoamBlock"):
                self.node.addChild(self.drawBlock(job))
            if self.visible("ShowWorkingPlanes"):
                self.node.addChild(self.drawWorkingPlanes(job))
            if self.visible("ShowOrigin"):
                self.node.addChild(self.drawOrigin(job))
            if self.visible("ShowRotationAxis") and job.FiveAxisMachine:
                self.node.addChild(self.drawRotationAxis(job))
        except Exception as error:
            App.Console.PrintWarning("Could not draw Job graphics: {}\n".format(error))

    def drawVolume(self, job):
        width = float(job.FieldWidth)
        travel = float(job.HorizontalTravel)
        height = float(job.VerticalTravel)
        x = -width / 2.0
        y = -float(job.OriginX)
        return _box(x, y, 0.0, width, travel, height,
                    (0.65, 0.65, 0.65), 0.9, (0.55, 0.55, 0.55))

    def drawBlock(self, job):
        position = job.BlockPosition
        return _box(
            float(position.x), float(position.y), float(position.z),
            float(job.BlockWidth), float(job.BlockLength), float(job.BlockHeight),
            (1.0, 0.45, 0.65), 0.8, (0.9, 0.2, 0.4))

    def drawWorkingPlanes(self, job):
        group = coin.SoSeparator()
        planes = utilities.getWorkingPlanes(job, job.Document)
        if planes is None:
            return group
        for plane in planes:
            x = plane.Position.x
            y = plane.Position.y
            z = plane.Position.z
            points = [
                (x, y, z),
                (x, y + plane.Length, z),
                (x, y + plane.Length, z + plane.Width),
                (x, y, z + plane.Width),
            ]
            group.addChild(_face(points, (1.0, 0.9, 0.05), 0.8))
            for i in range(4):
                group.addChild(_line([points[i], points[(i + 1) % 4]], (1.0, 0.85, 0.05), 1))
        return group

    def drawOrigin(self, job):
        group = coin.SoSeparator()
        half = float(job.FieldWidth) / 2.0
        for x, is_right in ((-half, False), (half, True)):
            transform = coin.SoTransform()
            transform.translation.setValue(x, 0, 0)
            origin = coin.SoSeparator()
            origin.addChild(transform)
            origin.addChild(_origin_axis("XR" if is_right else "XL", 100, False, is_right, (0, 1, 0)))
            origin.addChild(_origin_axis("YR" if is_right else "YL", 100, True, is_right, (1, 0, 0)))
            group.addChild(origin)
        return group

    def drawRotationAxis(self, job):
        y = float(job.OriginRotationX)
        length = float(job.VerticalTravel) + 50.0
        return _line([(0.0, y, 0.0), (0.0, y, length)], (1.0, 0.85, 0.05), 1.5, 0.5)
