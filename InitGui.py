# -*- coding: utf-8 -*-

__title__= "FreeCAD Foamcut Workbench - Init file"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPLv2.1"
__url__ = ["http://www.freecadweb.org"]

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui

class FoamcutWB (Workbench):
    def __init__(self):
        import os
        import utilities
        self.__class__.MenuText = "FoamCut"
        self.__class__.ToolTip = "Foamcut workbench provide functionality to prepare job and generate Gcode for 4 or 5 axis cnc hotwire cutter."
        self.__class__.Icon = utilities.getIconPath("foamcut.svg")

    def Initialize(self):
        "This function is executed when FreeCAD starts"
        # import here all the needed files that create your FreeCAD commands
        import utilities
        import InitMachine 
        import Path
        import Enter
        import Exit
        import Move
        import Join
        import Rotate
        import Route
        import Postprocess
        
        self.examples = [] # A list of command names to create example project
        self.list = [
            "InitMachine", 
            "MakePath", 
            "MakeEnter", 
            "MakeExit", 
            "MakeMove", 
            "Join", 
            "Rotate", 
            "Route", 
            "MakeGcode"] # A list of command names created in the line above
        
        self.appendToolbar("FoamCut",self.list) # creates a new toolbar with your commands
        self.appendMenu("FoamCut",self.list) # creates a new menu
        self.appendMenu("FoamCut",self.examples) # creates a new menu

    def Activated(self):
        "This function is executed when the workbench is activated"
        return

    def Deactivated(self):
        "This function is executed when the workbench is deactivated"
        return

    def ContextMenu(self, recipient):
        "This is executed whenever the user right-clicks on screen"
        # "recipient" will be either "view" or "tree"
        self.appendContextMenu("FoamCut",self.list) # add commands to the context menu

    def GetClassName(self): 
        # this function is mandatory if this is a full python workbench
        return "Gui::PythonWorkbench"
       
Gui.addWorkbench(FoamcutWB())