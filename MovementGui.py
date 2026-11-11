# -*- coding: utf-8 -*-

__title__ = "Movement task panels"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Shared task panel machinery for movement objects."

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
from PySide import QtGui
import utilities

MOVE_COMMON_PROPERTIES = ["FeedRate", "WirePower", "RapidMove", "AddPause", "PauseDuration"]


class MovementTaskPanel:
    '''Base task panel for movement objects.

    Edits the object and recomputes only that object, so the preview is cheap.
    Routes using the object are updated on OK or by the explicit Preview route button.
    '''

    def __init__(self, obj, created = False):
        self.obj = obj
        self.created = created
        self._status_error = False

        self._original = {}
        for name in self.properties():
            if hasattr(obj, name):
                self._original[name] = (getattr(obj, name), utilities.getPropertyExpression(obj, name))

        self._doc = obj.Document
        if self._doc.getBookedTransactionID() == 0:
            self._doc.openTransaction(self.title())

        self.form = QtGui.QWidget()
        self.form.setWindowTitle(self.title())

        layout = QtGui.QFormLayout(self.form)
        layout.setContentsMargins(10, 6, 10, 6)
        self.addObjectSection(layout)
        self.addCommonSection(layout)

        self.preview()

    def title(self):
        return "{} [{}]".format(self.obj.Type, self.obj.Label)

    def properties(self):
        names = list(self.objectProperties()) + list(MOVE_COMMON_PROPERTIES)
        if self.hasCompensationDirection():
            names.append("CompensationDirection")
        return names

    def objectProperties(self):
        return []

    def hasCompensationDirection(self):
        return self.obj.Type not in ("Path", "Projection") and hasattr(self.obj, "CompensationDirection")

    def addObjectSection(self, layout):
        pass

    def applyObjectValues(self):
        pass

    def addCommonSection(self, layout):
        feed_expression = utilities.getPropertyExpression(self.obj, "FeedRate")
        feed_value, feed_unit, self._feed_factor = utilities.getPreferredValue(
            FreeCAD.Units.Quantity(float(self.obj.FeedRate), FreeCAD.Units.Velocity))

        self._feed_override = QtGui.QCheckBox("Override feed rate", self.form)
        self._feed_override.setChecked(feed_expression is None)
        self._feed_override.toggled.connect(self.onFeedOverrideToggled)

        self._feed = QtGui.QDoubleSpinBox(self.form)
        self._feed.setRange(0.0, 1000000.0)
        self._feed.setDecimals(2)
        self._feed.setSuffix(" {}".format(feed_unit))
        self._feed.setValue(feed_value)
        self._feed.setEnabled(feed_expression is None)
        self._feed.valueChanged.connect(self.preview)
        layout.addRow(self._feed_override, self._feed)

        power_expression = utilities.getPropertyExpression(self.obj, "WirePower")

        self._power_override = QtGui.QCheckBox("Override wire power", self.form)
        self._power_override.setChecked(power_expression is None)
        self._power_override.toggled.connect(self.onPowerOverrideToggled)

        self._power = QtGui.QSpinBox(self.form)
        self._power.setRange(0, 100000)
        self._power.setValue(int(self.obj.WirePower))
        self._power.setEnabled(power_expression is None)
        self._power.valueChanged.connect(self.preview)
        layout.addRow(self._power_override, self._power)

        self._rapid = QtGui.QCheckBox("Rapid move", self.form)
        self._rapid.setChecked(bool(self.obj.RapidMove))
        self._rapid.stateChanged.connect(self.preview)
        layout.addRow("", self._rapid)

        self._pause = QtGui.QCheckBox("Add pause at the end", self.form)
        self._pause.setChecked(bool(self.obj.AddPause))
        self._pause.stateChanged.connect(self.onPauseToggled)

        pause_quantity = FreeCAD.Units.Quantity("{} s".format(float(self.obj.PauseDuration)))
        pause_value, pause_unit, self._pause_factor = utilities.getPreferredValue(pause_quantity)

        self._pause_duration = QtGui.QDoubleSpinBox(self.form)
        self._pause_duration.setRange(0.0, 100000.0)
        self._pause_duration.setDecimals(2)
        self._pause_duration.setSuffix(" {}".format(pause_unit))
        self._pause_duration.setValue(pause_value)
        self._pause_duration.setEnabled(bool(self.obj.AddPause))
        self._pause_duration.valueChanged.connect(self.preview)
        layout.addRow(self._pause, self._pause_duration)

        if self.hasCompensationDirection():
            self._compensation = QtGui.QComboBox(self.form)
            self._compensation.addItems(utilities.FC_KERF_DIRECTIONS)
            self._compensation.setCurrentText(self.obj.CompensationDirection)
            self._compensation.currentIndexChanged.connect(self.preview)
            layout.addRow("Kerf direction:", self._compensation)
        else:
            self._compensation = None

        self._preview_route = QtGui.QPushButton("Preview route", self.form)
        self._preview_route.setSizePolicy(QtGui.QSizePolicy.Maximum, QtGui.QSizePolicy.Fixed)
        self._preview_route.clicked.connect(self.previewRoute)
        self._preview_route.setVisible(len(self.routes()) > 0)
        layout.addRow("", self._preview_route)

        self._status = QtGui.QLabel("Route is updated on OK or by Preview route.", self.form)
        self._status.setWordWrap(True)
        layout.addRow(self._status)

    def routes(self):
        proxy = getattr(self.obj, "Proxy", None)
        if proxy is None or not hasattr(proxy, "getRoutes"):
            return []
        return proxy.getRoutes(self.obj)

    def onFeedOverrideToggled(self, checked):
        self._feed.setEnabled(checked)
        if checked:
            self._feed.setValue(float(self.obj.FeedRate) / self._feed_factor)
        self.preview()
        if not checked:
            self._feed.setValue(float(self.obj.FeedRate) / self._feed_factor)

    def onPowerOverrideToggled(self, checked):
        self._power.setEnabled(checked)
        if checked:
            self._power.setValue(int(self.obj.WirePower))
        self.preview()
        if not checked:
            self._power.setValue(int(self.obj.WirePower))

    def onPauseToggled(self, state):
        self._pause_duration.setEnabled(self._pause.isChecked())
        self.preview()

    def applyCommonValues(self):
        if self._feed_override.isChecked():
            utilities.overrideProperty(self.obj, "FeedRate", float(self._feed.value()) * self._feed_factor)
        else:
            expression = self._original.get("FeedRate", (None, None))[1]
            utilities.restorePropertyExpression(self.obj, "FeedRate", expression)

        if self._power_override.isChecked():
            utilities.overrideProperty(self.obj, "WirePower", int(self._power.value()))
        else:
            expression = self._original.get("WirePower", (None, None))[1]
            utilities.restorePropertyExpression(self.obj, "WirePower", expression)

        self.obj.RapidMove = self._rapid.isChecked()
        self.obj.AddPause = self._pause.isChecked()
        self.obj.PauseDuration = float(self._pause_duration.value()) * self._pause_factor

        if self._compensation is not None:
            self.obj.CompensationDirection = self._compensation.currentText()

    def applyValues(self):
        self.applyObjectValues()
        self.applyCommonValues()

    def preview(self):
        '''Apply widget values and recompute the object only; return False on error.'''
        try:
            self.applyValues()
            self.obj.recompute()
        except Exception as error:
            self.setStatus(str(error), True)
            return False

        self.setStatus("Preview updated (route is updated on OK or by Preview route).", False)
        return True

    def previewRoute(self):
        if not self.preview():
            return

        try:
            for route in self.routes():
                # - Recompute the route inputs first: route.recompute() alone
                #   does not refresh touched dependencies
                for object in route.Objects:
                    object.recompute()
                route.touch()
                route.recompute()
        except Exception as error:
            self.setStatus(str(error), True)
            return

        self.setStatus("Route preview updated.", False)

    def setStatus(self, text, is_error):
        self._status.setText(text)
        self._status.setStyleSheet("color: red;" if is_error else "")

    def restoreOriginal(self):
        for name, (value, expression) in self._original.items():
            if expression:
                utilities.restorePropertyExpression(self.obj, name, expression)
            else:
                utilities.clearPropertyExpression(self.obj, name)
                setattr(self.obj, name, value)

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)

    def accept(self):
        if not self.preview():
            return True
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
            if doc.getObject(self.obj.Name) is not None:
                doc.removeObject(self.obj.Name)
        else:
            self.restoreOriginal()
        Gui.Control.closeDialog()
        doc.recompute()
        return True


class MoveTaskPanel(MovementTaskPanel):
    '''Task panel for the Move movement object.'''

    def objectProperties(self):
        return ["MoveX", "MoveY"]

    def addObjectSection(self, layout):
        x_value, length_unit, self._length_factor = utilities.getPreferredValue(
            FreeCAD.Units.Quantity(float(self.obj.MoveX), FreeCAD.Units.Length))

        self._move_x = QtGui.QDoubleSpinBox(self.form)
        self._move_x.setRange(-100000.0, 100000.0)
        self._move_x.setDecimals(2)
        self._move_x.setSuffix(" {}".format(length_unit))
        self._move_x.setValue(x_value)
        self._move_x.valueChanged.connect(self.preview)
        layout.addRow("Move X:", self._move_x)

        self._move_y = QtGui.QDoubleSpinBox(self.form)
        self._move_y.setRange(-100000.0, 100000.0)
        self._move_y.setDecimals(2)
        self._move_y.setSuffix(" {}".format(length_unit))
        self._move_y.setValue(float(self.obj.MoveY) / self._length_factor)
        self._move_y.valueChanged.connect(self.preview)
        layout.addRow("Move Y:", self._move_y)

    def applyObjectValues(self):
        self.obj.MoveX = float(self._move_x.value()) * self._length_factor
        self.obj.MoveY = float(self._move_y.value()) * self._length_factor


PANELS = {
    "Move": MoveTaskPanel,
}


def showMovementPanel(obj, created = False):
    '''
    Open the task panel for a movement object.
    @returns True when a panel was opened
    '''
    if obj is None:
        return False

    panel_class = PANELS.get(getattr(obj, "Type", None))
    if panel_class is None:
        return False

    Gui.Control.showDialog(panel_class(obj, created))
    return True


def openMovementPanel(obj):
    '''
    Open the edit panel for an existing movement object (double-click).
    '''
    return showMovementPanel(obj, False)
