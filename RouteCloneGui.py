# -*- coding: utf-8 -*-

__title__ = "Duplicate route"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "GUI for the route clone: view provider, task panel and command."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
from PySide import QtGui
import RouteGui
import WireRoute
import WireRouteClone
import utilities


class WireRouteCloneVP(RouteGui.WireRouteVP):

    def drawRoute(self):
        source = self.Object.Source
        while self.node.getNumChildren() > 0:
            self.node.removeChild(0)

        if source is None:
            return

        points_L, points_R = self.Object.Proxy.getOutputPoints(self.Object)
        if len(points_L) == 0 or len(points_R) == 0:
            return

        breaks = self.sourceBreaks(source)
        self.node.addChild(self.drawRouteLines(points_L, breaks))
        self.node.addChild(self.drawRouteLines(points_R, breaks))

        if source.Pauses is not None and len(source.Pauses) > 0 and len(source.Pauses) == len(source.PausesDurations):
            pauses = []
            for dur_idx, idx in enumerate(source.Pauses):
                duration = source.PausesDurations[dur_idx]
                pauses.append([points_L[idx], float(duration)])
                pauses.append([points_R[idx], float(duration)])
            self.node.addChild(self.drawPauses(pauses))

    def sourceBreaks(self, source):
        '''Break indexes from the source layout; fall back to its stored values.'''
        try:
            return WireRoute.getRouteBreaks(source)
        except Exception:
            return list(source.RouteBreaks)

    def getIcon(self):
        return utilities.getIconPath("route-clone.svg")

    def claimChildren(self):
        source = self.Object.Source
        if source is None:
            return []
        return [source]

    def onDelete(self, obj, subelements):
        return True

    def updateData(self, obj, prop):
        if prop == "Redraw" or prop == "Position" or prop == "Mirror" or prop == "Source":
            self.drawRoute()

    def doubleClicked(self, obj):
        showRouteClonePanel(self.Object, False)
        return True


class RouteCloneTaskPanel:
    '''Task panel for creating and editing a route clone.'''

    def __init__(self, clone, created = False):
        self.clone = clone
        self.created = created
        self.original_position = App.Vector(clone.Position)
        self.original_mirror = clone.Mirror
        self.original_source = clone.Source

        self._doc = clone.Document
        if self._doc.getBookedTransactionID() == 0:
            self._doc.openTransaction("Route clone")

        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Route clone")

        layout = QtGui.QFormLayout(self.form)
        layout.setContentsMargins(10, 6, 10, 6)

        self._source = QtGui.QComboBox(self.form)
        current_source = clone.Source
        job = clone.Document.getObject(clone.JobName)
        for route in WireRouteClone.getJobRoutes(job):
            self._source.addItem("{} ({})".format(route.Label, route.Name), route.Name)
        index = self._source.findData(current_source.Name) if current_source is not None else -1
        self._source.setCurrentIndex(index)
        layout.addRow("Source:", self._source)

        y_value, length_unit, self._length_factor = utilities.getPreferredValue(
            App.Units.Quantity(float(clone.Position.y), App.Units.Length))
        self._length_unit = length_unit

        self._y = QtGui.QDoubleSpinBox(self.form)
        self._y.setRange(-100000.0, 100000.0)
        self._y.setDecimals(3)
        self._y.setSuffix(" {}".format(length_unit))
        self._y.setValue(y_value)
        layout.addRow("Y offset:", self._y)

        self._z = QtGui.QDoubleSpinBox(self.form)
        self._z.setRange(-100000.0, 100000.0)
        self._z.setDecimals(3)
        self._z.setSuffix(" {}".format(length_unit))
        self._z.setValue(float(clone.Position.z) / self._length_factor)
        layout.addRow("Z offset:", self._z)

        self._mirror_yz = QtGui.QCheckBox("Mirror horizontally (YZ)", self.form)
        self._mirror_yz.setChecked(clone.Mirror in ("YZ", "YZ+XY"))
        layout.addRow("", self._mirror_yz)

        self._mirror_xy = QtGui.QCheckBox("Mirror vertically (XY)", self.form)
        self._mirror_xy.setChecked(clone.Mirror in ("XY", "YZ+XY"))
        layout.addRow("", self._mirror_xy)

        try:
            pivot = clone.Proxy.getPivotZ(clone)
            pivot_value, pivot_unit, _ = utilities.getPreferredValue(App.Units.Quantity(pivot, App.Units.Length))
            layout.addRow("XY pivot:", QtGui.QLabel("{:.2f} {} (block mid-height)".format(pivot_value, pivot_unit)))
        except Exception:
            layout.addRow("XY pivot:", QtGui.QLabel("-"))

        self._result = QtGui.QLabel("")
        self._result.setWordWrap(True)
        layout.addRow("Result:", self._result)

        self._status = QtGui.QLabel("")
        self._status.setWordWrap(True)
        layout.addRow(self._status)

        for widget in (self._y, self._z):
            widget.valueChanged.connect(self.preview)
        self._source.currentIndexChanged.connect(self.sourceChanged)
        self._mirror_yz.stateChanged.connect(self.preview)
        self._mirror_xy.stateChanged.connect(self.preview)

        self.preview()

    def getStandardButtons(self):
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        # - PySide6 returns a StandardButton enum that is not int-convertible
        return buttons.value if hasattr(buttons, "value") else int(buttons)

    def sourceChanged(self):
        name = self._source.currentData()
        if not name:
            return

        source = self.clone.Document.getObject(name)
        if source is None:
            return

        self.clone.Source = source
        self.preview()

    def position(self):
        return App.Vector(0.0,
                          self._y.value() * self._length_factor,
                          self._z.value() * self._length_factor)

    def mirror(self):
        yz = self._mirror_yz.isChecked()
        xy = self._mirror_xy.isChecked()
        if yz and xy:
            return "YZ+XY"
        if yz:
            return "YZ"
        if xy:
            return "XY"
        return "None"

    def preview(self):
        '''Apply the current widget values to the clone, validate and redraw. Return False when invalid.'''
        position = self.position()
        mirror = self.mirror()

        self.clone.Position = position
        self.clone.Mirror = mirror

        try:
            points_L, points_R = self.clone.Proxy.validatePosition(self.clone, position, mirror)
            self._status.setText("")
            self._status.setStyleSheet("")
        except Exception as error:
            self._status.setText(str(error))
            self._status.setStyleSheet("color: red;")
            self.redraw()
            return False

        all_points = points_L + points_R
        if all_points:
            ys = [point.y / self._length_factor for point in all_points]
            zs = [point.z / self._length_factor for point in all_points]
            self._result.setText("Y {:.2f}..{:.2f} {}   Z {:.2f}..{:.2f} {}".format(
                min(ys), max(ys), self._length_unit, min(zs), max(zs), self._length_unit))
        else:
            self._result.setText("-")

        self.redraw()
        return True

    def redraw(self):
        view_object = getattr(self.clone, "ViewObject", None)
        if view_object is not None and getattr(view_object, "Proxy", None) is not None:
            try:
                view_object.Proxy.drawRoute()
            except Exception:
                pass

    def accept(self):
        if not self.preview():
            return True  # keep the panel open, the validation message is visible
        doc = self._doc
        doc.commitTransaction()
        Gui.Control.closeDialog()
        # - Recompute after closing: document recompute is deferred while a task panel is open
        doc.recompute()
        return True

    def reject(self):
        doc = self._doc
        doc.abortTransaction()
        if self.created:
            if doc.getObject(self.clone.Name) is not None:
                doc.removeObject(self.clone.Name)
        else:
            self.clone.Source = self.original_source
            self.clone.Position = self.original_position
            self.clone.Mirror = self.original_mirror
        Gui.Control.closeDialog()
        doc.recompute()
        return True


def showRouteClonePanel(clone, created = False):
    panel = RouteCloneTaskPanel(clone, created)
    Gui.Control.showDialog(panel)


class DuplicateRoute():
    """Duplicate route"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("route-clone.svg"),
                'Accel' : "",
                "MenuText": "Duplicate route",
                "ToolTip" : "Create a parametric clone of the selected route, place and mirror it."}

    def Activated(self):
        doc = App.ActiveDocument
        group = utilities.requireActiveJob("Cannot duplicate route", doc)
        if group is None:
            return
        if not hasattr(group, "FieldWidth"):
            # - Pre-0.2.1 document; the migration must run first, otherwise the
            #   clone would read a stale source route.
            return

        selection = Gui.Selection.getSelectionEx()
        source = selection[0].Object if len(selection) == 1 else None
        if not WireRouteClone.canDuplicateRoute(source) or source.JobName != group.Name:
            return

        clone = None
        try:
            clone = WireRouteClone.createRouteClone(group, source, recompute = False)
            WireRouteCloneVP(clone.ViewObject)

            Gui.Selection.clearSelection()
            doc.recompute()
            Gui.Selection.addSelection(doc.Name, clone.Name)
            showRouteClonePanel(clone, created = True)
        except Exception as error:
            App.Console.PrintError("Failed to create Route clone.\n")
            if clone is not None:
                doc.removeObject(clone.Name)
            App.Console.PrintError("{}\n".format(error))

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False

        group = utilities.getActiveJob()
        if group is None or not hasattr(group, "FieldWidth"):
            return False

        selection = Gui.Selection.getSelectionEx()
        if len(selection) != 1:
            return False

        route = selection[0].Object
        return WireRouteClone.canDuplicateRoute(route) and route.JobName == group.Name


Gui.addCommand("DuplicateRoute", DuplicateRoute())
