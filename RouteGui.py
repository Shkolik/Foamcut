# -*- coding: utf-8 -*-

__title__ = "Route task panel"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Task panel for Route objects."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
from PySide import QtGui
import math
import pivy.coin as coin
import utilities
import FoamCutViewProviders
from TaskPanelBase import BaseTaskPanel
import WireRoute
from utilities import getIconPath, setPickStyle, UNPICKABLE, FC_TYPES_TO_ROUTE


class RouteTaskPanel(BaseTaskPanel):
    '''Task panel for route kerf compensation settings.'''

    def properties(self):
        return ["KerfCompensation", "CompensationDirection", "CompensationStrategy", "CompensationDegree"]

    def addSections(self, layout):
        self.addOverrideRow(layout, "KerfCompensation", "kerf compensation",
                            App.Units.Quantity(float(self.obj.KerfCompensation), App.Units.Length),
                            decimals = 3)

        self._direction = QtGui.QComboBox(self.form)
        self._direction.addItems(utilities.FC_ROUTE_KERF_DIRECTIONS)
        self._direction.setCurrentText(self.obj.CompensationDirection)
        self._direction.currentIndexChanged.connect(self.preview)
        layout.addRow("Kerf direction:", self._direction)

        self._strategy = QtGui.QComboBox(self.form)
        self._strategy.addItems(utilities.FC_KERF_STRATEGY)
        self._strategy.setCurrentText(self.obj.CompensationStrategy)
        self._strategy.currentIndexChanged.connect(self.preview)
        layout.addRow("Kerf strategy:", self._strategy)

        self.addOverrideRow(layout, "CompensationDegree", "compensation degree",
                            App.Units.Quantity(float(self.obj.CompensationDegree)),
                            decimals = 3)

        self._preview_route = QtGui.QPushButton("Preview route", self.form)
        self._preview_route.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        self._preview_route.clicked.connect(self.previewRoute)
        layout.addRow("", self._preview_route)

    def applyValues(self):
        self.obj.CompensationDirection = self._direction.currentText()
        self.obj.CompensationStrategy = self._strategy.currentText()

    def previewObject(self):
        pass

    def previewMessage(self):
        return "Changes applied. Press Preview route or OK to rebuild the route."

    def previewRoute(self):
        try:
            self.applyValues()
            self.applyOverrides()
            self.applyLengthRows()
            self.obj.touch()
            self.obj.recompute()
        except Exception as error:
            self.setStatus(str(error), True)
            return

        self.setStatus("Route preview updated.", False)

    def reject(self):
        doc = self._doc
        route_name = self.obj.Name
        sources = list(self.obj.Objects) if self.created else []
        job = doc.getObject(self.obj.JobName)

        doc.abortTransaction()
        if self.created:
            if doc.getObject(route_name) is not None:
                doc.removeObject(route_name)
            if job is not None:
                for source in sources:
                    if source.Document is not None and source not in job.Group:
                        job.addObject(source)
        else:
            self.restoreOriginal()
        Gui.Control.closeDialog()
        doc.recompute()
        return True


def showRoutePanel(obj, created = False):
    if obj is None:
        return False
    Gui.Control.showDialog(RouteTaskPanel(obj, created))
    return True


def openRoutePanel(obj):
    return showRoutePanel(obj, False)


def splitRoutePoints(points, breaks):
    '''
    Split a flattened route polyline into the segments separated by breaks.
    A break marks the last point of one segment; the next segment starts at
    the following point, so no line is drawn across a rapid or a rotation.
    @param points - route point list (Offset_L or Offset_R)
    @param breaks - indexes of the last point of every segment but the last
    @returns list of point lists
    '''
    if len(points) == 0:
        return []
    if len(breaks) == 0:
        return [list(points)]

    pointGroups = []
    lastBreak = 0
    for idx in breaks:
        pointGroups.append(list(points[lastBreak:idx + 1]))
        lastBreak = idx + 1
    if lastBreak < len(points):
        pointGroups.append(list(points[lastBreak:]))
    return pointGroups


class WireRouteVP(FoamCutViewProviders.FoamCutBaseViewProvider):

    def doubleClicked(self, _):
        return openRoutePanel(self.Object)

    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object

        self.node = coin.SoGroup()

        self.drawRoute()
        obj.addDisplayMode(self.node, "Flat Lines")
        setPickStyle(obj, UNPICKABLE)

    def drawRoute(self):
        if self.Object.Offset_L is not None and self.Object.Offset_R is not None and len(self.Object.Offset_L) > 0 and len(self.Object.Offset_R) > 0:
            while self.node.getNumChildren() > 0:
                self.node.removeChild(0)

            breaks = self.routeBreaks()
            self.node.addChild(self.drawRouteLines(self.Object.Offset_L, breaks))
            self.node.addChild(self.drawRouteLines(self.Object.Offset_R, breaks))

            if self.Object.Pauses is not None and len(self.Object.Pauses) > 0 and len(self.Object.Pauses) == len(self.Object.PausesDurations):
                pauses = []
                for dur_idx, idx in enumerate(self.Object.Pauses):
                    dur = self.Object.PausesDurations[dur_idx]
                    pauses.append([self.Object.Offset_L[idx], float(dur)])
                    pauses.append([self.Object.Offset_R[idx], float(dur)])

                self.node.addChild(self.drawPauses(pauses))

    def routeBreaks(self):
        '''
        Break indexes from the route point layout. Routes saved before the
        layout-based accounting keep stale indexes in RouteBreaks, so use the
        layout when it is consistent with the stored points.
        '''
        try:
            return WireRoute.getRouteBreaks(self.Object)
        except Exception:
            return list(self.Object.RouteBreaks)

    def drawPauses(self, points):
        group = coin.SoGroup()
        if len(points) > 0:
            color = coin.SoBaseColor()
            color.rgb.setValue(1, 0, 0)
            draw_style = coin.SoDrawStyle()
            draw_style.style = coin.SoDrawStyle.FILLED
            draw_style.lineWidth = 1
            group.addChild(draw_style)
            group.addChild(color)

            # points is array of pauses each item is also array, where first element is point coordinates and second is pause duration
            for i in range(len(points)):
                sep = coin.SoSeparator()

                # Define the coordinates of the circle
                coords = coin.SoCoordinate3()
                num_segments = 20
                radius = points[i][1]
                circle_coords = []
                for idx in range(num_segments):
                    angle = 2.0 * math.pi * idx / num_segments
                    x = radius * math.cos(angle)
                    y = radius * math.sin(angle)
                    circle_coords.append((x, y, 0))
                coords.point.setValues(0, num_segments, circle_coords)

                faceSet = coin.SoFaceSet()
                faceSet.numVertices.setValue(num_segments)

                point = points[i][0]
                transform = coin.SoTransform()
                transform.translation.setValue(point.x, point.y, point.z)

                rotation = coin.SbRotation(coin.SbVec3f(0, 1, 0), math.radians(90))
                transform.rotation.setValue(rotation)

                shapeHints = coin.SoShapeHints()
                shapeHints.vertexOrdering = coin.SoShapeHints.CLOCKWISE

                sep.addChild(coords)
                sep.addChild(transform)
                sep.addChild(shapeHints)
                sep.addChild(faceSet)

                group.addChild(sep)

        return group

    def drawRouteLines(self, points, breaks):
        group = coin.SoGroup()
        for pointGroup in splitRoutePoints(points, breaks):
            group.addChild(self.drawRouteLine(pointGroup))
        return group

    def drawRouteLine(self, points):
        sep = coin.SoSeparator()
        if len(points) > 0:
            line = coin.SoLineSet()
            line.numVertices.setValue(len(points))
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, [[p.x, p.y, p.z] for p in points])
            color = coin.SoBaseColor()
            color.rgb.setValue(1, 0, 0)
            draw_style = coin.SoDrawStyle()
            draw_style.style = coin.SoDrawStyle.FILLED
            draw_style.lineWidth = 2
            sep.addChild(draw_style)
            sep.addChild(color)
            sep.addChild(coords)
            sep.addChild(line)
        return sep

    def getIcon(self):
        return getIconPath("route.svg")

    def getDisplayModes(self, obj):
        """Return the display modes that this viewprovider supports."""
        return ["Flat Lines"]

    def claimChildren(self):
        return [object for object in self.Object.Objects]

    def onDelete(self, obj, subelements):
        doc = self.Object.Document if self.Object is not None else None
        if doc is None:
            doc = App.ActiveDocument
        if doc is not None:
            group = doc.getObject(self.Object.JobName)
            if group is not None and group.Type == "Job":
                for object in self.Object.Objects:
                    group.addObject(object)
        return True

    def updateData(self, obj, prop):
        if prop == "Redraw":#prop == "Offset_L" or prop == "Offset_R" or prop == "Pauses" or prop == "PausesDurations":
            self.drawRoute()


class MakeRoute():
    """Make Route"""

    def GetResources(self):
        return {"Pixmap"  : getIconPath("route.svg"),
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create a route",
                "ToolTip" : "Create a route from selected objects."}

    def Activated(self):
        doc = App.ActiveDocument
        group = utilities.requireActiveJob("Cannot create Route", doc)
        if group is None:
            return
        if not hasattr(group, "FieldWidth"):
            # - Pre-0.2.1 document; the migration must run before routes
            #   can bind to the Job configuration.
            return

        # - Get selecttion
        objects = [item.Object for item in Gui.Selection.getSelectionEx()]

        route = None
        label = ""
        try:
            # - Create object
            route = WireRoute.createRoute(group, objects, recompute = False)
            WireRouteVP(route.ViewObject)

            doc.recompute()
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, route.Name)

            showRoutePanel(route, created = True)
        except Exception as error:
            App.Console.PrintError(f"Failed to create Route.\n")
            if route:
                label = f"{route.Label}: "
                doc.removeObject(route.Name)
            App.Console.PrintError(f"{label}{error}\n")

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False

        group = utilities.getActiveJob()
        if group is None:
            return False

        # - Pre-0.2.1 documents are not migrated yet: their settings
        #   are not on the Job, so the route would bind broken
        #   expressions. Let the migration run first.
        if not hasattr(group, "FieldWidth"):
            return False

        # - Get selected objects
        objects = [item.Object for item in Gui.Selection.getSelectionEx()]

        # - nothing selected
        if len(objects) == 0:
            return False

        for obj in objects:
            if not hasattr(obj, "Type") or obj.Type not in FC_TYPES_TO_ROUTE:
                return False
        return True


Gui.addCommand("Route", MakeRoute())
