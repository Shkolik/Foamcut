# -*- coding: utf-8 -*-

__title__ = "Movement task panels"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Task panels for movement objects."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
from PySide import QtGui
import utilities
from TaskPanelBase import BaseTaskPanel

MOVE_COMMON_PROPERTIES = ["RapidMove", "AddPause", "PauseDuration"]


class MovementTaskPanel(BaseTaskPanel):
    '''Task panel for movement objects.

    Edits the object and recomputes only that object, so the preview is cheap.
    Routes using the object are updated on OK or by the explicit Preview route button.
    '''

    def properties(self):
        names = list(self.objectProperties()) + list(MOVE_COMMON_PROPERTIES)
        # - Feed and power are per-object only on Move and Join; Enter, Exit,
        #   Path and Projection inherit the config values in the postprocessor.
        if hasattr(self.obj, "FeedRate"):
            names.append("FeedRate")
        if hasattr(self.obj, "WirePower"):
            names.append("WirePower")
        if self.hasCompensationDirection():
            names.append("CompensationDirection")
        return names

    def objectProperties(self):
        return []

    def hasCompensationDirection(self):
        return hasattr(self.obj, "CompensationDirection")

    def addSections(self, layout):
        self.addObjectSection(layout)
        self.addCommonSection(layout)

    def addObjectSection(self, layout):
        pass

    def applyValues(self):
        self.applyObjectValues()
        self.applyCommonValues()

    def applyObjectValues(self):
        pass

    def previewMessage(self):
        return "Preview updated (route is updated on OK or by Preview route)."

    def addCommonSection(self, layout):
        self._feed_override = None
        self._feed = None
        self._feed_factor = 1.0
        if hasattr(self.obj, "FeedRate"):
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

        self._power_override = None
        self._power = None
        if hasattr(self.obj, "WirePower"):
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
        if self._feed_override is not None:
            if self._feed_override.isChecked():
                utilities.overrideProperty(self.obj, "FeedRate", float(self._feed.value()) * self._feed_factor)
            else:
                expression = self._original.get("FeedRate", (None, None))[1]
                utilities.restorePropertyExpression(self.obj, "FeedRate", expression)

        if self._power_override is not None:
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


class MoveTaskPanel(MovementTaskPanel):
    '''Task panel for the Move movement object.'''

    def objectProperties(self):
        return ["MoveX", "MoveY"]

    def addObjectSection(self, layout):
        self._move_x = self.addLengthRow(layout, "MoveX", "Move X:")
        self._move_y = self.addLengthRow(layout, "MoveY", "Move Y:")

    def applyObjectValues(self):
        pass


class JoinTaskPanel(MovementTaskPanel):
    '''Task panel for the Join movement object.'''


class PathTaskPanel(MovementTaskPanel):
    '''Task panel for the Path movement object.'''


class ProjectionTaskPanel(MovementTaskPanel):
    '''Task panel for the Projection movement object.'''


class EnterTaskPanel(MovementTaskPanel):
    '''Task panel for the Enter movement object.'''

    def objectProperties(self):
        return ["SafeHeight", "LeadInEnabled", "LeadInX", "LeadInY"]

    def addObjectSection(self, layout):
        self.addOverrideRow(layout, "SafeHeight", "safe height",
                            FreeCAD.Units.Quantity(float(self.obj.SafeHeight), FreeCAD.Units.Length))

        self._lead = QtGui.QCheckBox("Add lead-in", self.form)
        self._lead.setChecked(bool(self.obj.LeadInEnabled))
        self._lead.toggled.connect(self.onLeadToggled)
        layout.addRow("", self._lead)

        self._lead_x = self.addLengthRow(layout, "LeadInX", "Lead-in X:")
        self._lead_y = self.addLengthRow(layout, "LeadInY", "Lead-in Y:")
        self._lead_x.setEnabled(self._lead.isChecked())
        self._lead_y.setEnabled(self._lead.isChecked())

    def onLeadToggled(self, checked):
        self._lead_x.setEnabled(checked)
        self._lead_y.setEnabled(checked)
        self.preview()

    def applyValues(self):
        self.obj.LeadInEnabled = self._lead.isChecked()
        self.applyCommonValues()


class ExitTaskPanel(MovementTaskPanel):
    '''Task panel for the Exit movement object.'''

    def objectProperties(self):
        return ["SafeHeight", "LeadOutEnabled", "LeadOutX", "LeadOutY"]

    def addObjectSection(self, layout):
        self.addOverrideRow(layout, "SafeHeight", "safe height",
                            FreeCAD.Units.Quantity(float(self.obj.SafeHeight), FreeCAD.Units.Length))

        self._lead = QtGui.QCheckBox("Add lead-out", self.form)
        self._lead.setChecked(bool(self.obj.LeadOutEnabled))
        self._lead.toggled.connect(self.onLeadToggled)
        layout.addRow("", self._lead)

        self._lead_x = self.addLengthRow(layout, "LeadOutX", "Lead-out X:")
        self._lead_y = self.addLengthRow(layout, "LeadOutY", "Lead-out Y:")
        self._lead_x.setEnabled(self._lead.isChecked())
        self._lead_y.setEnabled(self._lead.isChecked())

    def onLeadToggled(self, checked):
        self._lead_x.setEnabled(checked)
        self._lead_y.setEnabled(checked)
        self.preview()

    def applyValues(self):
        self.obj.LeadOutEnabled = self._lead.isChecked()
        self.applyCommonValues()


PANELS = {
    "Move": MoveTaskPanel,
    "Join": JoinTaskPanel,
    "Path": PathTaskPanel,
    "Projection": ProjectionTaskPanel,
    "Enter": EnterTaskPanel,
    "Exit": ExitTaskPanel,
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
