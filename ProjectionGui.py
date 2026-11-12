# -*- coding: utf-8 -*-

__title__ = "Projection GUI"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "Projection view provider and command."

import FreeCAD
App = FreeCAD
import FreeCADGui
Gui = FreeCADGui
import FoamCutViewProviders
import MovementGui
import utilities
from utilities import getAllSelectedObjects, getWorkingPlanes, getEdgesLinks
import WireProjection


class ProjectionSectionVP(FoamCutViewProviders.FoamCutMovementViewProvider):
    def getIcon(self):
        return utilities.getIconPath("projection.svg")

    def claimChildren(self):
        if self.Object.Source is not None and len(self.Object.Source) > 0:
            return [self.Object.Source[0]]
        return None


class MakeProjection():
    """Make Projection"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("projection.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create Projection",
                "ToolTip" : "Create projection object from selected face, edge or vertex. Separate projection will be created for each edge or vertex."}

    def CreateFromEdge(self, edge, group):
        projection = None
        label = ""
        try:
            projection = WireProjection.createProjection(group, (edge[0], (edge)[1][0]), recompute = False)
            ProjectionSectionVP(projection.ViewObject)
            projection.ViewObject.PointSize = 4
        except Exception as error:
            App.Console.PrintError(f"Failed to create Projection.\n")
            if projection:
                label = f"{projection.Label}: "
                projection.Document.removeObject(projection.Name)
            App.Console.PrintError(f"{label}{error}\n")
            projection = None

        return projection

    def Activated(self):
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        setActive = False
        # - if machine is not active, try to select first one in a document
        if group is None or group.Type != "Job":
            group = App.ActiveDocument.getObject("Job")
            setActive = True

        if group is not None and group.Type == "Job":
            if setActive:
                Gui.ActiveDocument.ActiveView.setActiveObject("group", group)

            # - Get selected objects
            objects = getAllSelectedObjects(True)

            baseObjects = []

            created = []
            for object in objects:
                if object[1][0].startswith("Face"):
                    # - prepare base object.
                    # - Sometimes, after reopening file it is necessary to recompute em or list of edges will be empty
                    if object[0].Name not in baseObjects:
                        object[0].touch()
                        baseObjects.append(object[0].Name)
                        object[0].recompute(True)

                    edges = getEdgesLinks(object[0], object[0].getSubObject(object[1][0]))

                    if len(edges) == 0:
                        FreeCAD.Console.PrintError("ERROR: No edges of the selected face [{}] match the object shape. Select edges directly instead.\n".format(object[0].Label))
                        return

                    for edge in edges:
                        projection = self.CreateFromEdge(edge, group)
                        if projection is not None:
                            created.append(projection)
                else:
                    projection = self.CreateFromEdge(object, group)
                    if projection is not None:
                        created.append(projection)

            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()

            if len(created) == 1:
                Gui.Selection.addSelection(App.ActiveDocument.Name, created[0].Name)
                MovementGui.showMovementPanel(created[0], created = True)
            elif created:
                for projection in created:
                    Gui.Selection.addSelection(App.ActiveDocument.Name, projection.Name)
                App.Console.PrintMessage("{} projections created. Double-click a projection to edit settings.\n".format(len(created)))

    def IsActive(self):
        if App.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            # - if machine is not active, try to select first one in a document
            if group is None or group.Type != "Job":
                group = App.ActiveDocument.getObject("Job")

            if group is not None and group.Type == "Job":
                # - Get selected objects including Faces
                objects = getAllSelectedObjects(True)

                # - at least one Edge, Vertex or Face should be selected
                if len(objects) == 0:
                    return False

                wp = getWorkingPlanes(group, App.ActiveDocument)
                if wp is None or len(wp) != 2:
                    return False
                return True
            return False


Gui.addCommand("MakeProjection", MakeProjection())
