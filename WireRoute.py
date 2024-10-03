# -*- coding: utf-8 -*-

__title__ = "Create Route"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Create a route from selected pathes."
__usage__ = """Select multiple paths in order of cutting and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
import Part
import FoamCutBase
import FoamCutViewProviders
import utilities
from utilities import isMovement
import pivy.coin as coin

class WireRoute(FoamCutBase.FoamCutBaseObject):
    def __init__(self, obj, objects, jobName):   
        super().__init__(obj, jobName)     
        obj.Type = "Route"  
        
        obj.addProperty("App::PropertyString",    "Error", "", "", 5) 

        obj.addProperty("App::PropertyLinkList",    "Objects",          "Task",   "Source data").Objects = objects
        obj.addProperty("App::PropertyIntegerList", "Data",             "Task",   "Data")
        obj.addProperty("App::PropertyBoolList",    "DataDirection",    "Task",   "Data Direction")
        obj.addProperty("App::PropertyLength",      "KerfCompensation", "", "", 5) # - no used for now, and, probably, will not

        config = self.getConfigName(obj)

        obj.setExpression(".KerfCompensation", u"<<{}>>.KerfCompensation".format(config))

        obj.Proxy = self
        self.execute(obj)
    
    def execute(self, obj): 
        obj.Error = ""

        first       = obj.Objects[0]
        reversed    = None        # - Second segment is reversed
        START       = 0           # - Segment start point index
        END         = -1          # - Segment end point index
        route_data  = []
        route_data_dir  = []
        item_index  = 0

        # - Check is single element
        if len(obj.Objects) == 1:
            # - Store element            
            route_data.append(item_index)
            route_data_dir.append(False)

        # - Walk through other objects
        for second in obj.Objects[1:]:
            item_index += 1

            # - Process skipped element
            if first is None:
                first = second
                if first.Type == "Enter":
                    route_data.append(item_index)
                    route_data_dir.append(True) #enter is always reversed

                print("SKIP: %s" % second.Type)
                continue
            
            if first.Type == "Projection" and first.PointsCount < 2:
                print("Vertex Projection - skip")
                first = second
                continue

            # - Skip rotation object
            if first.Type == "Rotation":
                print("R1")
                # - Store first element
                route_data.append(item_index - 1)
                route_data_dir.append(False)

                # - Check is rotation is firts element
                if item_index == 1:
                    # - Do not skip next element
                    first = second
                    continue
                else:
                    # - Go to next object
                    first = None
                    continue
            elif second.Type == "Rotation":
                print("R1 - 2")
                # - Store element
                route_data.append(item_index)
                route_data_dir.append(False)

                # - Skip element
                first = None
                continue
            elif first.Type == "Exit" and second.Type == "Enter":
                print("EXIT -> ENTER")
                # - Store first item
                if len(route_data) == 0:
                    # - Store element
                    route_data.append(item_index - 1)
                    route_data_dir.append(False)

                # - Store element
                route_data.append(item_index)
                route_data_dir.append(True) #enter is always reversed

                first = second
                continue
            
            # - Get lines on left plane
            if isMovement(first) or first.Type == "Enter":
                first_line  = first.Path_L
            else:
                obj.Error = "ERROR: {} - Unsupported first element. Second = {}".format(first.Label, second.Label)
                App.Console.PrintError(obj.Error)
                return False
            
            if isMovement(second) or second.Type == "Exit": 
                second_line = second.Path_L
            else:
                obj.Error = "ERROR: {} - Unsupported second element. First = {}".format(second.Label, first.Label)
                App.Console.PrintError(obj.Error)
                return False
            
            if reversed is None:
                first_reversed = False

                # - Detect first pair
                if utilities.isCommonPoint(first_line[END], second_line[START]):
                    print ("First connected: FWD - FWD")
                    reversed = False
                elif utilities.isCommonPoint(first_line[END], second_line[END]):
                    print ("First connected: FWD - REV")
                    reversed = True
                elif utilities.isCommonPoint(first_line[START], second_line[START]):
                    print ("First connected: REV - FWD")
                    first_reversed  = True
                    reversed        = False
                elif utilities.isCommonPoint(first_line[START], second_line[END]):
                    print ("First connected: REV - REV")
                    first_reversed  = True
                    reversed        = True
                else:
                    obj.Error = "ERROR: {} not connected with {}".format(first.Label, second.Label)
                    App.Console.PrintError(obj.Error)
                    return False
                
                # - Store first element
                route_data.append(item_index - 1)
                route_data_dir.append(first_reversed)

                # - Store second element
                route_data.append(item_index)
                route_data_dir.append(reversed)
            else:
                # - Detect next pairs
                if utilities.isCommonPoint(first_line[START if reversed else END], second_line[START]):
                    print ("Connected: FWD - FWD")
                    reversed = False
                elif utilities.isCommonPoint(first_line[START if reversed else END], second_line[END]):
                    print ("Connected: FWD - REV")
                    reversed = True
                else:
                    obj.Error = "ERROR: {} not connected with {}".format(first.Label, second.Label)
                    App.Console.PrintError(obj.Error)
                    return False

                # - Store next element
                route_data.append(item_index)
                route_data_dir.append(reversed)

            # - Go to next object
            first = second
        
        if len(route_data) != len(route_data_dir) or len(route_data) == 0:
            obj.Error("Error: Data calculation error.")
            App.Console.PrintError(obj.Error)
            return False
        
        obj.Data = route_data
        obj.DataDirection = route_data_dir


class WireRouteVP(FoamCutViewProviders.FoamCutBaseViewProvider):
    
    def attach(self, obj):
        self.ViewObject = obj
        self.Object = obj.Object
        
        self.node = coin.SoGroup()

        self.drawRoute()
        obj.addDisplayMode(self.node, "Flat Lines")
        utilities.setPickStyle(obj, utilities.UNPICKABLE)

    def drawRoute(self):
        while self.node.getNumChildren() > 0:
            self.node.removeChild(0)

        pointsLeft = []
        pointsRight = []

        pauses = []

        # - Walk throug all route elemets
        for i in range(len(self.Object.Data)):                                
            # - Access item
            item = self.Object.Data[i]

            object = self.Object.Objects[item]
    
            pointsLeft.extend(object.Path_L[::-1] if self.Object.DataDirection[i] else object.Path_L)
            pointsRight.extend(object.Path_R[::-1] if self.Object.DataDirection[i] else object.Path_R)
            
            if hasattr(object, "AddPause") and object.AddPause:
                index = 0 if self.Object.DataDirection[i] else -1
                pauses.append([object.Path_L[index], float(object.PauseDuration)])
                pauses.append([object.Path_R[index], float(object.PauseDuration)])

        self.node.addChild(self.drawRouteLine(pointsLeft))
        self.node.addChild(self.drawRouteLine(pointsRight))

        self.node.addChild(self.drawPauses(pauses))

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

            # points is array of pauses each item is also array, where first element is poin coordinates and second is pause duration
            for i in range(len(points)):
                sep = coin.SoSeparator()
                sphere = coin.SoSphere()
                sphere.radius = points[i][1]

                translation = coin.SoTranslation()
                translation.translation.setValue(points[i][0].x, points[i][0].y, points[i][0].z)
                sep.addChild(translation)
                sep.addChild(sphere)

                group.addChild(sep)

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
        return utilities.getIconPath("route.svg")

    def getDisplayModes(self, obj):
        """Return the display modes that this viewprovider supports."""
        return ["Flat Lines"]
    
    def claimChildren(self):
        return [object for object in self.Object.Objects]
    
    def onDelete(self, obj, subelements):
        group = App.ActiveDocument.getObject(self.Object.JobName)
        if group is not None and group.Type == "Job":
            for object in self.Object.Objects:
                group.addObject(object)
        return True
    
    def updateData(self, obj, prop):
        if prop == "Data" or prop == "DataDirection" or prop == "Objects":
            self.drawRoute()
        

class MakeRoute():
    """Make Route"""

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("route.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Create a route",
                "ToolTip" : "Create a route from selected paths"}

    def Activated(self): 
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":        
            # - Get selecttion
            objects = [item.Object for item in Gui.Selection.getSelectionEx()]
            
            # - Create object
            route = group.newObject("App::FeaturePython", "Route")
            WireRoute(route, objects, group.Name)
            WireRouteVP(route.ViewObject)

            for obj in objects:
                obj.ViewObject.Visibility = False
                group.removeObject(obj)

            App.ActiveDocument.recompute()
            Gui.Selection.clearSelection()
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            if group is not None and group.Type == "Job":
                # - Get selected objects
                objects = [item.Object for item in Gui.Selection.getSelectionEx()]

                # - nothing selected
                if len(objects) == 0:
                    return False
                
                for obj in objects:
                    if not hasattr(obj, "Type") or obj.Type not in utilities.FC_TYPES_TO_ROUTE:
                        return False                    
                return True
            return False
            
Gui.addCommand("Route", MakeRoute())
