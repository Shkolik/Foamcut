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

    def getAxisMapping(self):
        '''
        Get axis names from active document MachineConfig
        @returns tuple of (X1AxisName, Z1AxisName, X2AxisName, Z2AxisName, R1AxisName)
        '''
        defaults = ("X", "Y", "Z", "A", "B")
        doc = App.ActiveDocument
        if doc is None:
            return defaults
        job = doc.getObject("Job")
        if job is None or not hasattr(job, "ConfigName"):
            return defaults
        config = doc.getObject(job.ConfigName)
        if config is None:
            return defaults
        return (
            config.X1AxisName if hasattr(config, "X1AxisName") else "X",
            config.Z1AxisName if hasattr(config, "Z1AxisName") else "Y",
            config.X2AxisName if hasattr(config, "X2AxisName") else "Z",
            config.Z2AxisName if hasattr(config, "Z2AxisName") else "A",
            config.R1AxisName if hasattr(config, "R1AxisName") else "B",
        )

    def mirrorGcode(self, file: str):

        App.Console.PrintMessage("> Reading source file {}\n".format(file))

        # - Read axis mapping from active document config (defaults when not available)
        x1, z1, x2, z2, r1 = self.getAxisMapping()

        # - Axis regex fragments
        number = r'([\-]{0,1}[0-9]+\.[0-9]+)'
        feed = r'F([0-9]+\.[0-9]+)'
        ax1 = re.escape(x1)
        az1 = re.escape(z1)
        ax2 = re.escape(x2)
        az2 = re.escape(z2)
        ar1 = re.escape(r1)

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
                rt = re.search(r'^(G0[01]) %s%s %s' % (ar1, number, feed), line)
                if rt is not None:
                    CM = rt.group(1)
                    RT = float(rt.group(2))
                    FR = float(rt.group(3))
                    out_data.append("%s %s%.2f F%.1f\n" % (CM, r1, -RT if RT != 0 else 0, FR))
                    continue

                withPowerChange = True
                mv = re.search(r'^(G0[01]) %s%s %s%s %s%s %s%s %s S%s' % (ax1, number, az1, number, ax2, number, az2, number, feed, number), line)
                if mv is None:
                    withPowerChange = False
                    mv = re.search(r'^(G0[01]) %s%s %s%s %s%s %s%s %s' % (ax1, number, az1, number, ax2, number, az2, number, feed), line)
                     
                if mv is not None:
                    if withPowerChange:
                        CM = mv.group(1)
                        LX = float(mv.group(2))
                        LY = float(mv.group(3))
                        RX = float(mv.group(4))
                        RY = float(mv.group(5))
                        FR = float(mv.group(6))
                        PW = float(mv.group(7))
                        out_data.append("%s %s%.2f %s%.2f %s%.2f %s%.2f F%.1f S%.2f\n" % (CM, x1, RX, z1, RY, x2, LX, z2, LY, FR, PW))
                        continue
                    else:
                        CM = mv.group(1)
                        LX = float(mv.group(2))
                        LY = float(mv.group(3))
                        RX = float(mv.group(4))
                        RY = float(mv.group(5))
                        FR = float(mv.group(6))
                        out_data.append("%s %s%.2f %s%.2f %s%.2f %s%.2f F%.1f\n" % (CM, x1, RX, z1, RY, x2, LX, z2, LY, FR))
                        continue

                # - Direct copy line
                out_data.append(line + ("" if line.endswith("\n") else "\n"))


        fileName = re.sub(r'\.gcode$', '-mirror.gcode', file, flags=re.IGNORECASE)
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
