# -*- coding: utf-8 -*-

__title__ = "Job GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Job view provider, inline machine graphics, configuration task panel and Init machine command."

import math
import re
import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
from PySide import QtGui
import pivy.coin as coin
import utilities
import FoamCutViewProviders
import JobConfig
from InitMachine import createMachine
from TaskPanelBase import BaseTaskPanel
from FoamCutViewProviders import drawLine as _line, drawFace as _face, drawBox as _box

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
        self.applySelectionPolicy(obj)

    def finishRestoring(self):
        # - View properties are restored after attach; apply the policy again.
        self.applySelectionPolicy(getattr(self, "ViewObject", None))

    def applySelectionPolicy(self, view_object):
        '''Keep the Job from painting its decoration in the selection color.

        A group view provider has no Selectable property, so the selection
        style is reduced to a bounding box. The decoration itself is already
        unpickable, and the Job panel clears the selection when it opens.
        '''
        if view_object is not None and hasattr(view_object, "SelectionStyle"):
            view_object.SelectionStyle = "BoundBox"

    def getIcon(self):
        return utilities.getIconPath("machine.svg")

    def doubleClicked(self, obj):
        # - Editing the Job config replaces the old activate/deactivate toggle.
        #   Double-clicking a setup also makes it the target for new objects.
        #   An unmigrated Job returns False and keeps the default double-click.
        job = getattr(obj, "Object", None)
        if job is None:
            return False
        utilities.setActiveJob(job)
        return showJobPanel(job)

    def setupContextMenu(self, obj, menu):
        '''Tree context menu: activate this setup or edit its settings.'''
        job = getattr(obj, "Object", None)
        if job is None or getattr(job, "Type", None) != "Job":
            return

        # - Kept as plain actions: the bold tree entry already shows which
        #   setup is active, and clearing the active Job is not useful.
        menu.addAction("Activate").triggered.connect(
            lambda checked = False, target = job: utilities.setActiveJob(target))
        menu.addAction("Edit setup").triggered.connect(
            lambda checked = False, target = job: showJobPanel(target))

    def updateData(self, obj, prop):
        if hasattr(self, "node") and prop not in ("Group", "Label", "Proxy"):
            self.draw()
            self.refreshRotationBlocks()

    def onChanged(self, obj, prop):
        if hasattr(self, "node") and (prop in VIEW_PROPERTY_NAMES or prop == "Visibility"):
            self.draw()

    def refreshRotationBlocks(self):
        '''
        Redraw the foam block visual of the rotations after a Job change.
        The block belongs to the Job, but the Rotation draws it, and a Job change
        does not recompute the rotations, so they are refreshed from here.
        '''
        for child in getattr(self.Object, "Group", []):
            if getattr(child, "Type", "") != "Rotation":
                continue

            view_object = getattr(child, "ViewObject", None)
            proxy = getattr(view_object, "Proxy", None) if view_object is not None else None
            if proxy is None or not hasattr(proxy, "drawBlock"):
                continue

            try:
                proxy.drawBlock()
            except Exception as error:
                App.Console.PrintWarning("Could not draw the rotated foam block: {}\n".format(error))

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


DEFAULT_GROUP = "General"

# - Last edited group, so reopening the panel returns to it.
_LAST_GROUP = None

# - Page order of the Job task panel; groups not listed are appended at the end.
GROUP_ORDER = (
    "Machine Geometry",
    "Foam Block",
    "Travel",
    "Axis Mapping",
    "FeedRate",
    "Wire",
    "Kerf Compensation",
    "Homing/Parking",
    "GCODE",
)

# - Property groups presented together in the panel. The property editor keeps
#   its own groups; only the task panel merges them.
PANEL_GROUPS = {
    "Homing": "Homing/Parking",
    "Parking": "Homing/Parking",
}

# - Preferred row order per group; properties not listed follow alphabetically.
PROPERTY_ORDER = {
    "Machine Geometry": (
        "FiveAxisMachine", "HorizontalTravel", "VerticalTravel",
        "FieldWidth", "OriginX", "OriginRotationX",
    ),
    "Foam Block": ("BlockWidth", "BlockLength", "BlockHeight", "BlockPosition"),
    "Travel": ("SafeHeight", "PauseDuration"),
    "Axis Mapping": ("X1AxisName", "Z1AxisName", "X2AxisName", "Z2AxisName", "R1AxisName"),
    "FeedRate": ("FeedRateCut", "FeedRateMove", "FeedRateRotate"),
    "Wire": (
        "WireMinPower", "WireMaxPower", "DynamicWirePower",
        "WireStretchVerification", "WireStretchLength",
    ),
    "Kerf Compensation": ("KerfCompensation", "CompensationDegree"),
    "Homing/Parking": (
        "EnableHoming", "HomingX1", "HomingZ1", "HomingX2", "HomingZ2", "HomingR1",
        "EnableParking", "ParkX", "ParkZ", "ParkR1",
    ),
    "GCODE": (
        "FeedRateMode", "TimeUnits", "CommentStyle", "DiscretizationStep",
        "CutCommand", "MoveCommand", "PauseCommand", "WireOnCommand",
        "WireOffCommand", "HomingCommand", "InitPositionCommand",
        "StartProgramCode", "EndProgramCode",
    ),
}

# - Property types displayed with a unit-aware spin box.
UNIT_TYPES = frozenset((
    "App::PropertyAngle",
    "App::PropertyDistance",
    "App::PropertyLength",
    "App::PropertySpeed",
    "App::PropertyTime",
))

SUPPORTED_TYPES = UNIT_TYPES | frozenset((
    "App::PropertyBool",
    "App::PropertyEnumeration",
    "App::PropertyFloat",
    "App::PropertyInteger",
    "App::PropertyPosition",
    "App::PropertyString",
    "App::PropertyVector",
))


def propertyLabel(name):
    '''
    Turn a property name into a human readable label.
    @param name - property name
    @returns label string, e.g. X1AxisName -> X1 axis name
    '''
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name).replace("_", " ").split()
    labels = []
    for index, word in enumerate(words):
        if len(word) == 1:
            labels.append(word.upper())
        elif index == 0:
            labels.append(word[:1].upper() + word[1:].lower())
        else:
            labels.append(word.lower())
    return " ".join(labels)


def supportsPropertyType(type_id):
    '''
    Check whether the Job panel knows how to edit a property type.
    @param type_id - App property type id, e.g. App::PropertyLength
    '''
    return type_id in SUPPORTED_TYPES


def panelProperties(obj):
    '''
    Return the Job task panel content as (group, property names) pairs.
    Properties are grouped like the property editor, except that groups listed
    in PANEL_GROUPS are presented together. A group is shown when it has at
    least one property that is not hidden. Hidden properties stay in their
    group so they can appear when another setting enables them.
    @param obj - Job object
    @returns list of tuples (group name, list of property names)
    '''
    grouped = {}
    for name in JobConfig.configPropertyNames(obj):
        group = obj.getGroupOfProperty(name) or DEFAULT_GROUP
        grouped.setdefault(PANEL_GROUPS.get(group, group), []).append(name)

    ordered = []
    for group in GROUP_ORDER:
        if group in grouped and isGroupVisible(obj, grouped[group]):
            ordered.append((group, orderedProperties(group, grouped[group])))
    for group in sorted(grouped):
        if group not in GROUP_ORDER and isGroupVisible(obj, grouped[group]):
            ordered.append((group, orderedProperties(group, grouped[group])))
    return ordered


def isGroupVisible(obj, names):
    '''
    A group gets a page when at least one of its properties is not hidden.
    '''
    return any("Hidden" not in obj.getEditorMode(name) for name in names)


def orderedProperties(group, names):
    '''
    Order the rows of a group: the preferred order first, then the rest.
    '''
    preferred = [name for name in PROPERTY_ORDER.get(group, ()) if name in names]
    return preferred + [name for name in names if name not in preferred]


class JobPropertyRow:
    '''A single property editor row in the Job task panel.'''

    def __init__(self, name, layout, index, label, widget, read):
        self.name = name
        self.layout = layout
        self.index = index
        self.label = label
        self.widget = widget
        self.read = read

    def setVisible(self, visible):
        if hasattr(self.layout, "setRowVisible") and hasattr(self.layout, "isRowVisible"):
            self.layout.setRowVisible(self.index, visible)
        else:
            self.label.setVisible(visible)
            self.widget.setVisible(visible)

    def isVisible(self):
        if hasattr(self.layout, "isRowVisible"):
            return bool(self.layout.isRowVisible(self.index))
        return self.label.isVisible()

    def setEnabled(self, enabled):
        self.label.setEnabled(enabled)
        self.widget.setEnabled(enabled)

    def setToolTip(self, text):
        self.label.setToolTip(text)
        self.widget.setToolTip(text)


class JobTaskPanel(BaseTaskPanel):
    '''Task panel for the Job machine and process configuration.

    A group selector switches between the property groups; each page has one
    row per property. Values are unit-aware and only edited rows are written
    back, so opening or cancelling the panel never changes the setup. The Job
    view provider redraws on every preview.
    '''

    def title(self):
        return "Job settings [{}]".format(self.obj.Label)

    def properties(self):
        return JobConfig.configPropertyNames(self.obj)

    def addSections(self, layout):
        global _LAST_GROUP

        self._rows = {}
        self._dirty = set()
        self._groups = panelProperties(self.obj)
        names = [group for group, _ in self._groups]

        # - A selector instead of tabs: the task panel is narrow and the
        #   property groups do not fit on one tab row.
        self._selector = QtGui.QComboBox(self.form)
        self._selector.addItems(names)
        layout.addRow("Group:", self._selector)

        self._pages = QtGui.QStackedWidget(self.form)
        for group, properties in self._groups:
            self._pages.addWidget(self.makeGroupPage(group, properties))
        layout.addRow(self._pages)

        if not self.created and _LAST_GROUP in names:
            self._selector.setCurrentIndex(names.index(_LAST_GROUP))
        self._pages.setCurrentIndex(self._selector.currentIndex())
        self._selector.currentIndexChanged.connect(self.selectGroup)

        self.refreshRows()

    def selectGroup(self, index):
        global _LAST_GROUP
        if 0 <= index < len(self._groups):
            _LAST_GROUP = self._groups[index][0]
        self._pages.setCurrentIndex(index)

    def makeGroupPage(self, group, names):
        page = QtGui.QWidget(self.form)
        page_layout = QtGui.QFormLayout(page)
        page_layout.setContentsMargins(8, 8, 8, 8)
        page_layout.setVerticalSpacing(6)
        for name in names:
            self.addPropertyRow(page_layout, name)
        return page

    def addPropertyRow(self, layout, name):
        label = QtGui.QLabel(propertyLabel(name))
        widget, read = self.makeEditor(name)
        index = layout.rowCount()
        layout.addRow(label, widget)

        row = JobPropertyRow(name, layout, index, label, widget, read)
        row.setToolTip(self.propertyToolTip(name))
        self._rows[name] = row

    def propertyToolTip(self, name):
        return self.obj.getDocumentationOfProperty(name) or name

    def row(self, name):
        '''Return the editor row for a property name.'''
        return self._rows[name]

    def makeEditor(self, name):
        '''
        Create the editor widget and the value reader for a property.
        The reader returns the value in the property domain (base units for
        quantities, App.Vector for vectors).
        '''
        type_id = self.obj.getTypeIdOfProperty(name)
        value = getattr(self.obj, name)

        if type_id == "App::PropertyBool":
            widget = QtGui.QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(lambda checked, prop = name: self.onValueEdited(prop))
            return widget, lambda: widget.isChecked()

        if type_id in UNIT_TYPES:
            display, unit, factor = utilities.getPreferredValue(value)
            widget = self.numberEditor(display, unit)
            widget.valueChanged.connect(lambda number, prop = name: self.onValueEdited(prop))
            return widget, lambda: float(widget.value()) * factor

        if type_id == "App::PropertyFloat":
            widget = self.numberEditor(float(value), "", decimals = 4)
            widget.valueChanged.connect(lambda number, prop = name: self.onValueEdited(prop))
            return widget, lambda: float(widget.value())

        if type_id == "App::PropertyInteger":
            widget = QtGui.QSpinBox()
            widget.setRange(-1000000, 1000000)
            widget.setKeyboardTracking(False)
            widget.setValue(int(value))
            widget.valueChanged.connect(lambda number, prop = name: self.onValueEdited(prop))
            return widget, lambda: int(widget.value())

        if type_id == "App::PropertyEnumeration":
            widget = QtGui.QComboBox()
            widget.addItems(self.obj.getEnumerationsOfProperty(name))
            widget.setCurrentText(str(value))
            widget.currentIndexChanged.connect(lambda index, prop = name: self.onValueEdited(prop))
            return widget, lambda: widget.currentText()

        if type_id == "App::PropertyString":
            widget = QtGui.QLineEdit()
            widget.setText(str(value))
            widget.textChanged.connect(lambda text, prop = name: self.onValueEdited(prop))
            return widget, lambda: widget.text()

        if type_id == "App::PropertyPosition":
            return self.makeVectorEditor(name, value, unit_aware = True)

        if type_id == "App::PropertyVector":
            return self.makeVectorEditor(name, value, unit_aware = False)

        # - Unknown property type: show it, but never write it back.
        widget = QtGui.QLineEdit()
        widget.setText(str(value))
        widget.setReadOnly(True)
        return widget, None

    def numberEditor(self, value, unit, decimals = 3):
        spin = QtGui.QDoubleSpinBox()
        spin.setRange(-1000000.0, 1000000.0)
        spin.setDecimals(decimals)
        spin.setKeyboardTracking(False)
        if unit:
            spin.setSuffix(" {}".format(unit))
        spin.setValue(float(value))
        return spin

    def makeVectorEditor(self, name, value, unit_aware):
        if unit_aware:
            _, unit, factor = utilities.getPreferredValue(
                App.Units.Quantity(1.0, App.Units.Length))
        else:
            unit, factor = "", 1.0

        # - One component per row keeps the panel narrow enough for the task view.
        container = QtGui.QWidget()
        grid = QtGui.QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(2)

        spins = []
        for row, (axis, component) in enumerate(zip(("X", "Y", "Z"), (value.x, value.y, value.z))):
            axis_label = QtGui.QLabel(axis)
            axis_label.setToolTip(self.propertyToolTip(name))
            spin = self.numberEditor(float(component) / factor, unit)
            spin.setToolTip(self.propertyToolTip(name))
            spin.valueChanged.connect(lambda number, prop = name: self.onValueEdited(prop))
            grid.addWidget(axis_label, row, 0)
            grid.addWidget(spin, row, 1)
            spins.append(spin)
        grid.setColumnStretch(1, 1)

        def read():
            return App.Vector(*(float(spin.value()) * factor for spin in spins))

        return container, read

    def onValueEdited(self, name):
        '''Mark a row as edited and refresh the preview.'''
        self._dirty.add(name)
        self.preview()

    def applyValues(self):
        for name in sorted(self._dirty):
            row = self._rows.get(name)
            if row is None or row.read is None:
                continue
            # - A property driven by an expression is not the panel's to change.
            if utilities.hasPropertyExpression(self.obj, name):
                continue
            self.writeProperty(name, row.read())
        self._dirty.clear()

    def accept(self):
        self.commitPendingEdits()
        return super().accept()

    def commitPendingEdits(self):
        '''Interpret text typed into a spin box before the values are read.'''
        for row in self._rows.values():
            widgets = [row.widget] + row.widget.findChildren(QtGui.QAbstractSpinBox)
            for widget in widgets:
                if isinstance(widget, QtGui.QAbstractSpinBox):
                    widget.interpretText()

    def writeProperty(self, name, value):
        if self.sameValue(getattr(self.obj, name), value):
            return
        setattr(self.obj, name, value)

    @staticmethod
    def sameValue(current, value):
        '''Compare a current property value with a value read from an editor.'''
        if isinstance(value, App.Vector):
            return all(abs(float(first) - float(second)) < 1e-9
                       for first, second in zip((current.x, current.y, current.z),
                                                (value.x, value.y, value.z)))
        if isinstance(value, bool):
            return bool(current) == value
        if isinstance(value, str):
            return str(current) == value
        if isinstance(value, int):
            return int(current) == int(value)
        return abs(float(current) - float(value)) <= 1e-9 * max(1.0, abs(float(current)))

    def refreshRows(self):
        '''Sync row visibility and editability with the property editor modes.'''
        for name, row in self._rows.items():
            expression = utilities.getPropertyExpression(self.obj, name)
            mode = self.obj.getEditorMode(name)
            row.setVisible("Hidden" not in mode)
            row.setEnabled("ReadOnly" not in mode and expression is None and row.read is not None)
            if expression:
                row.setToolTip("Driven by expression: {}".format(expression))
            else:
                row.setToolTip(self.propertyToolTip(name))

    def previewObject(self):
        self.obj.recompute()
        self.refreshRows()

    def previewMessage(self):
        return "Preview updated. Objects in the Job are rebuilt when you press OK."

    def reject(self):
        if self.created:
            view = Gui.ActiveDocument.ActiveView if getattr(Gui, "ActiveDocument", None) is not None else None
            if view is not None and view.getActiveObject(utilities.ACTIVE_JOB_KEY) is self.obj:
                utilities.setActiveJob(None)
        return super().reject()


def showJobPanel(obj, created = False):
    '''
    Open the Job configuration panel.
    @returns True when a panel was opened
    '''
    if obj is None or getattr(obj, "Type", None) != "Job":
        return False
    if not hasattr(obj, "FieldWidth"):
        # - Job restored from a pre-0.2.1 document; migration has not run yet
        return False
    if Gui.Control.activeDialog():
        # - FreeCAD keeps one task dialog per document. Do not build a panel
        #   that cannot be shown: it would leave its transaction open.
        return False

    # - The Job is a setup container: keep it out of the selection while its
    #   settings are edited so the machine decoration is not repainted.
    if obj.Document is not None and Gui.Selection.isSelected(obj):
        Gui.Selection.removeSelection(obj)

    Gui.Control.showDialog(JobTaskPanel(obj, created))
    return True


def openJobPanel(obj):
    '''
    Open the Job panel for an existing Job (double-click).
    '''
    return showJobPanel(obj, False)


class InitMachine():
    """Init machine"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("foamcut.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Init machine",
                "ToolTip" : "Create the Job and edit machine geometry, working area and process settings"}

    def Activated(self):
        doc = App.ActiveDocument
        machine = None
        try:
            machine = createMachine(doc, recompute = False)
            MachineVP(machine.ViewObject)

            utilities.setActiveJob(machine)

            doc.recompute()
        except Exception as error:
            App.Console.PrintError("Failed to create Job.\n")
            if machine is not None and machine.Document is not None:
                doc.removeObject(machine.Name)
            App.Console.PrintError("{}\n".format(error))
            return

        try:
            showJobPanel(machine, created = True)
        except Exception as error:
            # - The Job is valid; only the editor failed to open.
            App.Console.PrintError("Could not open the Job task panel.\n")
            App.Console.PrintError("{}\n".format(error))

    def IsActive(self):
        # - A document can hold several setups; Init machine adds another one.
        return App.ActiveDocument is not None

Gui.addCommand("InitMachine", InitMachine())
