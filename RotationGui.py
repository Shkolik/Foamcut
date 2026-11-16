# -*- coding: utf-8 -*-

__title__ = "Rotation task panel"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Task panel for Rotation objects."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
from PySide import QtGui
import pivy.coin as coin
import utilities
import FoamCutViewProviders
from TaskPanelBase import BaseTaskPanel
import Rotate

# - Same look as the Job foam block
FOAM_BLOCK_FACE_COLOR = (1.0, 0.45, 0.65)
FOAM_BLOCK_EDGE_COLOR = (0.9, 0.2, 0.4)
FOAM_BLOCK_TRANSPARENCY = 0.8


class RotationTaskPanel(BaseTaskPanel):
    '''Task panel for the Rotation object.'''

    def properties(self):
        return ["Angle", "OriginRotationX"]

    def addSections(self, layout):
        angle_value, angle_unit, self._angle_factor = utilities.getPreferredValue(
            App.Units.Quantity(self.obj.Angle))

        self._angle = QtGui.QDoubleSpinBox(self.form)
        self._angle.setRange(-3600.0, 3600.0)
        self._angle.setDecimals(2)
        self._angle.setSuffix(" {}".format(angle_unit))
        self._angle.setValue(angle_value)
        self._angle.valueChanged.connect(self.preview)
        layout.addRow("Angle:", self._angle)

        self.addOverrideRow(layout, "OriginRotationX", "rotation origin",
                            App.Units.Quantity(float(self.obj.OriginRotationX), App.Units.Length))

        source = self.obj.Source.Label if self.obj.Source is not None else "-"
        layout.addRow("Source:", QtGui.QLabel(source, self.form))

    def applyValues(self):
        self.obj.Angle = float(self._angle.value()) * self._angle_factor

    def reject(self):
        source = self.obj.Source
        result = super().reject()
        if self.created and source is not None:
            try:
                source.ViewObject.Visibility = True
            except Exception:
                pass
        return result


def showRotationPanel(obj, created = False):
    if obj is None:
        return False
    Gui.Control.showDialog(RotationTaskPanel(obj, created))
    return True


def openRotationPanel(obj):
    return showRotationPanel(obj, False)


class RotationVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    def attach(self, obj):
        super().attach(obj)

        if not hasattr(obj, "ShowFoamBlock"):
            obj.addProperty("App::PropertyBool", "ShowFoamBlock", "Task",
                            "Show the foam block rotated with the part").ShowFoamBlock = \
                utilities.getParameterBool("RotationShowFoamBlock", True)

        self.node = coin.SoSeparator()
        obj.RootNode.addChild(self.node)

        self.drawBlock()
        self.hideSource()

    def drawBlock(self):
        '''
        Draw the Job foam block rotated around the machine rotation axis, so the
        stock position on the rotating table can be checked before cutting.
        '''
        if not hasattr(self, "node"):
            return

        while self.node.getNumChildren() > 0:
            self.node.removeChild(0)

        if not getattr(self.ViewObject, "Visibility", True) or not getattr(self.ViewObject, "ShowFoamBlock", True):
            return

        try:
            proxy = getattr(self.Object, "Proxy", None)
            if proxy is None or not hasattr(proxy, "getRotatedBlockCorners"):
                return

            corners = proxy.getRotatedBlockCorners(self.Object)
        except Exception as error:
            App.Console.PrintWarning("{}: cannot draw the rotated foam block: {}\n".format(self.Object.Label, error))
            return

        if corners is None:
            return

        # - Nodes added to the view provider root are transformed by the object
        #   placement, but the corners are already in machine coordinates, so
        #   compensate it.
        placement = getattr(self.Object, "Placement", None)
        if placement is not None:
            inverse = placement.inverse()
            corners = [inverse.multVec(point) for point in corners]

        # - Only the block is unpickable, the rotation shape stays selectable.
        pick_style = coin.SoPickStyle()
        pick_style.style.setValue(coin.SoPickStyle.UNPICKABLE)
        self.node.addChild(pick_style)

        self.node.addChild(FoamCutViewProviders.drawBoxCorners(
            corners, FOAM_BLOCK_FACE_COLOR, FOAM_BLOCK_TRANSPARENCY, FOAM_BLOCK_EDGE_COLOR))

    def hideSource(self):
        try:
            if self.Object.Source is not None and self.Object.Source.ViewObject is not None:
                self.Object.Source.ViewObject.Visibility = False
        except Exception:
            pass

    def updateData(self, obj, prop):
        if prop == "Source":
            self.hideSource()

        if prop not in ("Group", "Label", "Proxy"):
            self.drawBlock()

    def onChanged(self, obj, prop):
        if prop in ("ShowFoamBlock", "Visibility"):
            self.drawBlock()

    def getIcon(self):
        return utilities.getIconPath("rotation.svg")

    def doubleClicked(self, _):
        return openRotationPanel(self.Object)

    def claimChildren(self):
        return [self.Object.Source]

    def onDelete(self, obj, subelements):
        try:
            self.Object.Source.ViewObject.Visibility = True
        except Exception as err:
            App.Console.PrintError("Error in onDelete: {0} \n".format(err))
        return True


class AddRotation():
    """Add Rotation"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("rotation.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Rotate target",
                "ToolTip" : "Rotate target object by given angle around rotation axis"}

    def Activated(self):
        doc = App.ActiveDocument

        group = utilities.requireActiveJob("Cannot create Rotation", doc)
        if group is None:
            return

        source = Gui.Selection.getSelectionEx()[0].Object
        rt = None
        label = ""
        try:
            # - Create rotation object
            rt = Rotate.createRotation(group, source, recompute = False)
            RotationVP(rt.ViewObject)
            try:
                source.ViewObject.Visibility = False
            except Exception:
                pass

            Gui.Selection.clearSelection()
            doc.recompute()
            Gui.Selection.addSelection(doc.Name, rt.Name)

            showRotationPanel(rt, created = True)
        except Exception as error:
            App.Console.PrintError(f"Failed to create Rotation.\n")
            if rt:
                label = f"{rt.Label}: "
                doc.removeObject(rt.Name)
            App.Console.PrintError(f"{label}{error}\n")

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False

        group = utilities.getActiveJob()
        if group is None:
            return False

        # - Pre-0.2.1 documents are not migrated yet: their settings
        #   are not on the Job, so a new object would bind broken
        #   expressions. Let the migration run first.
        if not hasattr(group, "FieldWidth"):
            return False

        if not getattr(group, "FiveAxisMachine", False):
            return False

        # - Get selecttion
        selection = Gui.Selection.getSelectionEx()

        # - nothing selected
        if len(selection) == 0:
            return False

        # - Check object type
        if selection[0] is None or selection[0].Object is None:
            return False

        obj = selection[0].Object
        if not hasattr(obj, "Shape"):
            return False

        if (hasattr(obj, "Type") and
            (obj.Type == "Path" or obj.Type == "Enter"  or obj.Type == "Job" or obj.Type == "Helper" or obj.Type == "Config"
            or obj.Type == "Exit" or obj.Type == "Move" or obj.Type == "Join" or obj.Type == "Route" or obj.Type == "Projection")):
            return False

        return True


Gui.addCommand("Rotate", AddRotation())
