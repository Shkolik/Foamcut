# -*- coding: utf-8 -*-

__title__ = "View provider migration"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Reattach GUI view providers after the GUI modules were split from the domain modules."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui

from MoveGui import WireMoveVP
from EnterGui import WireEnterVP
from ExitGui import WireExitVP
from JoinGui import WireJoinVP
from PathGui import PathSectionVP
from ProjectionGui import ProjectionSectionVP
from RotationGui import RotationVP
from RouteGui import WireRouteVP
from RouteCloneGui import WireRouteCloneVP
from MachineGui import MachineVP


VIEW_PROVIDERS = {
    "Job": MachineVP,
    "Move": WireMoveVP,
    "Enter": WireEnterVP,
    "Exit": WireExitVP,
    "Join": WireJoinVP,
    "Path": PathSectionVP,
    "Projection": ProjectionSectionVP,
    "Rotation": RotationVP,
    "Route": WireRouteVP,
    "RouteClone": WireRouteCloneVP,
}

_observer = None


def restore(doc = None):
    '''
    Reattach the correct view provider to objects that lost it.
    Old documents stored the view provider class in the domain module
    (for example WirePath.PathSectionVP). The compatibility aliases in the
    domain modules restore those classes, but documents saved while the class
    was missing have no usable proxy and need this pass.
    @param doc (optional) - document to migrate; the active document by default
    @returns number of migrated objects
    '''
    if doc is None:
        doc = App.ActiveDocument
    if doc is None:
        return 0

    migrated = 0
    for obj in doc.Objects:
        view_provider = VIEW_PROVIDERS.get(getattr(obj, "Type", None))
        if view_provider is None:
            continue

        view_object = getattr(obj, "ViewObject", None)
        if view_object is None:
            continue

        if isinstance(getattr(view_object, "Proxy", None), view_provider):
            continue

        try:
            view_provider(view_object)
            migrated += 1
        except Exception as error:
            App.Console.PrintWarning(
                "Could not restore view provider for {}: {}\n".format(obj.Label, error))

    return migrated


class _DocumentObserver:
    def slotActivateDocument(self, doc):
        restore(doc)

    def slotFinishRestoreDocument(self, doc):
        restore(doc)


def install():
    '''Install the document observer once, from InitGui.'''
    global _observer
    if _observer is None:
        _observer = _DocumentObserver()
        App.addDocumentObserver(_observer)
    return _observer
