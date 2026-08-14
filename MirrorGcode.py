# -*- coding: utf-8 -*-

__title__ = "Mirror Gcode"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Mirror Gcode file around YZ plane."
__usage__ = """Select GCODE file to mirror."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
from PySide import QtGui
import utilities
import re

class MirrorG():
    """Mirror Gcode"""

    def mirrorGcode(self, file: str):

        App.Console.PrintMessage("> Reading source file {}\n".format(file))

        # - Read source file
        src_data = []
        with open(file, 'r') as f:
            src_data = f.read().splitlines()

        out_data = []
        mirror = False
        for line in src_data:
            if not mirror:
                # - Direct copy line
                out_data.append(line + ("" if line.endswith("\n") else "\n"))
 
                # - Find first move command
                if re.match('^(G0[01])', line):
                    mirror = True
                    continue
            else:
                # - Replace rotation
                rt = re.search(r'^(G0[01]) B([\-]{0,1}[0-9]+\.[0-9]+) F([0-9]+\.[0-9]+)', line)
                if rt is not None:
                    CM = rt.group(1)
                    RT = float(rt.group(2))
                    FR = float(rt.group(3))
                    out_data.append("%s B%.2f F%.1f\n" % (CM, -RT if RT != 0 else 0, FR))
                    continue

                withPowerChange = True
                mv = re.search(r'^(G0[01]) X([\-]{0,1}[0-9]+\.[0-9]+) Y([\-]{0,1}[0-9]+\.[0-9]+) Z([\-]{0,1}[0-9]+\.[0-9]+) A([\-]{0,1}[0-9]+\.[0-9]+) F([0-9]+\.[0-9]+) S([0-9]+\.[0-9]+)', line)
                if mv is None:
                    withPowerChange = False
                    mv = re.search(r'^(G0[01]) X([\-]{0,1}[0-9]+\.[0-9]+) Y([\-]{0,1}[0-9]+\.[0-9]+) Z([\-]{0,1}[0-9]+\.[0-9]+) A([\-]{0,1}[0-9]+\.[0-9]+) F([0-9]+\.[0-9]+)', line)
                     
                if mv is not None:
                    if withPowerChange:
                        CM = mv.group(1)
                        LX = float(mv.group(2))
                        LY = float(mv.group(3))
                        RX = float(mv.group(4))
                        RY = float(mv.group(5))
                        FR = float(mv.group(6))
                        PW = float(mv.group(7))
                        out_data.append("%s X%.2f Y%.2f Z%.2f A%.2f F%.1f S%.2f\n" % (CM, RX, RY, LX, LY, FR, PW))
                        continue
                    else:
                        CM = mv.group(1)
                        LX = float(mv.group(2))
                        LY = float(mv.group(3))
                        RX = float(mv.group(4))
                        RY = float(mv.group(5))
                        FR = float(mv.group(6))
                        out_data.append("%s X%.2f Y%.2f Z%.2f A%.2f F%.1f\n" % (CM, RX, RY, LX, LY, FR))
                        continue

                # - Direct copy line
                out_data.append(line + ("" if line.endswith("\n") else "\n"))


        fileName = file.replace(".gcode", "-mirror.gcode")
        # - Open save file dialog
        save_path, save_filter = QtGui.QFileDialog().getSaveFileName(None, "Save GCODE", fileName, "*.gcode") # PySide


        # - Check path
        if save_path == "":
            App.Console.PrintWarning("GCODE saving aborted (no output file path specified)\n")
        else:
            try:
                with open(save_path, "w") as f:
                    f.writelines(out_data)
                App.Console.PrintMessage("GCODE saved into [%s]\n" % save_path)
            except Exception:
                App.Console.PrintError("Unable to save GCODE in [" + save_path + "]\n")

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("mirrorgcode.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Mirror GCODE file",
                "ToolTip" : "Mirror selected GCODE file"}

    def Activated(self):
        dialog = QtGui.QFileDialog()
        lastDir = dialog.directory().absolutePath()
        # - Open save file dialog
        open_path, filter = dialog.getOpenFileName(None, "Open GCODE", lastDir, "*.gcode") # PySide

        App.Console.PrintMessage("Open file path: {}\n".format(open_path))

        # - Check path
        if open_path == "":
            App.Console.PrintWarning("Aborted (no file path specified)\n")
        else:
            self.mirrorGcode(open_path)

    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            return True
            
Gui.addCommand("MirrorGcode", MirrorG())
