# -*- coding: utf-8 -*-

__title__ = "Object task panel base"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Shared task panel base for Foamcut objects."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
from PySide import QtGui
import utilities


class BaseTaskPanel:
    '''Base task panel for editing a Foamcut object.

    Owns the transaction, the common OK/Cancel behaviour and the unit-aware
    override widgets. Subclasses provide the property list and their sections.
    '''

    def __init__(self, obj, created = False):
        self.obj = obj
        self.created = created

        self._original = {}
        for name in self.properties():
            if hasattr(obj, name):
                self._original[name] = (getattr(obj, name), utilities.getPropertyExpression(obj, name))

        self._overrides = {}
        self._length_rows = {}

        self._doc = obj.Document
        self._own_transaction = False
        if self._doc.getBookedTransactionID() == 0:
            self._doc.openTransaction(self.title())
            self._own_transaction = True

        try:
            self.form = QtGui.QWidget()
            self.form.setWindowTitle(self.title())

            layout = QtGui.QFormLayout(self.form)
            layout.setContentsMargins(10, 6, 10, 6)
            self.addSections(layout)
            self.addStatus(layout)

            self.preview()
        except Exception:
            if self._own_transaction and self._doc.getBookedTransactionID() != 0:
                self._doc.abortTransaction()
            raise

    def title(self):
        return "{} [{}]".format(self.obj.Type, self.obj.Label)

    def properties(self):
        return []

    def addSections(self, layout):
        pass

    def applyValues(self):
        pass

    def previewObject(self):
        self.obj.recompute()

    def previewMessage(self):
        return "Preview updated."

    def addStatus(self, layout):
        self._status = QtGui.QLabel(self.previewMessage(), self.form)
        self._status.setWordWrap(True)
        layout.addRow(self._status)

    def addOverrideRow(self, layout, prop, label, quantity, decimals = 2):
        '''Add a checkbox + unit-aware spin box that can detach a property from its expression.'''
        expression = utilities.getPropertyExpression(self.obj, prop)
        value, unit, factor = utilities.getPreferredValue(quantity)
        suffix = " {}".format(unit) if unit else ""

        check = QtGui.QCheckBox("Override {}".format(label), self.form)
        check.setChecked(expression is None)
        check.toggled.connect(lambda checked, name = prop: self.onOverrideToggled(name, checked))

        spin = QtGui.QDoubleSpinBox(self.form)
        spin.setRange(-1000000.0, 1000000.0)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setValue(value)
        spin.setEnabled(expression is None)
        spin.valueChanged.connect(self.preview)
        layout.addRow(check, spin)

        self._overrides[prop] = (check, spin, factor)
        return check, spin

    def onOverrideToggled(self, prop, checked):
        check, spin, factor = self._overrides[prop]
        spin.setEnabled(checked)
        if checked:
            spin.setValue(float(getattr(self.obj, prop)) / factor)
        self.preview()
        if not checked:
            spin.setValue(float(getattr(self.obj, prop)) / factor)

    def applyOverrides(self):
        for prop, (check, spin, factor) in self._overrides.items():
            if check.isChecked():
                utilities.overrideProperty(self.obj, prop, float(spin.value()) * factor)
            else:
                expression = self._original.get(prop, (None, None))[1]
                utilities.restorePropertyExpression(self.obj, prop, expression)

    def addLengthRow(self, layout, prop, label, decimals = 2):
        '''Add a unit-aware length spin box bound to a property.'''
        value, unit, factor = utilities.getPreferredValue(
            App.Units.Quantity(float(getattr(self.obj, prop)), App.Units.Length))
        suffix = " {}".format(unit) if unit else ""

        spin = QtGui.QDoubleSpinBox(self.form)
        spin.setRange(-1000000.0, 1000000.0)
        spin.setDecimals(decimals)
        spin.setSuffix(suffix)
        spin.setValue(value)
        spin.valueChanged.connect(self.preview)
        layout.addRow(label, spin)

        self._length_rows[prop] = (spin, factor)
        return spin

    def applyLengthRows(self):
        for prop, (spin, factor) in self._length_rows.items():
            setattr(self.obj, prop, float(spin.value()) * factor)

    def preview(self):
        '''Apply widget values and run the object preview. Return False on error.'''
        try:
            self.applyValues()
            self.applyOverrides()
            self.applyLengthRows()
            self.previewObject()
        except Exception as error:
            self.setStatus(str(error), True)
            return False

        self.setStatus(self.previewMessage(), False)
        return True

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
        buttons = QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        # - PySide6 returns a StandardButton enum that is not int-convertible
        return buttons.value if hasattr(buttons, "value") else int(buttons)

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
        name = self.obj.Name
        doc.abortTransaction()
        if self.created:
            if doc.getObject(name) is not None:
                doc.removeObject(name)
        else:
            self.restoreOriginal()
        Gui.Control.closeDialog()
        doc.recompute()
        return True
