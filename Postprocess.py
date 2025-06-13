# -*- coding: utf-8 -*-

__title__ = "Generate Gcode"
__author__ = "Andrew Shkolik & Andrei Bezborodov"
__license__ = "LGPL 2.1"
__doc__ = "Generate Gcode."
__usage__ = """Select route(s) and activate tool."""

import FreeCAD
App=FreeCAD
import FreeCADGui
Gui=FreeCADGui
from PySide import QtGui
import utilities
import os

class Postprocess():
    """Make Gcode"""

    '''
    Generate position string for travel
    '''
    def generateTravelPosition(self, config, X1, Z1, X2, Z2):
        return "%s%.2f %s%.2f %s%.2f %s%.2f" % (
            config.X1AxisName, float(X1) - float(config.OriginX),
            config.Z1AxisName, float(Z1),
            config.X2AxisName, float(X2) - float(config.OriginX),
            config.Z2AxisName, float(Z2)
            )

    '''
    Generate rotation position
    '''
    def generateRotationPosition(self, config, angle):
        return "%s%.2f" % (
            config.R1AxisName, float(angle)
        )

    '''
    Generate travel
    '''
    def generateTravel(self, config, command, feed_rate, wire_power, X1, Z1, X2, Z2):
        # - Create position
        position = self.generateTravelPosition(config, X1, Z1, X2, Z2)

        # - Create GCODE
        return command.replace("{Position}", str(position)).replace("{FeedRate}", str(float(feed_rate) * 60)).replace("{WirePower}", str(wire_power)) + "\r\n"

    '''
    Generate pause
    '''
    def generatePause(self, command, duration):
        return command.replace("{Duration}", "%.2f" %  float(duration)) + "\r\n"

    '''
    Generate rotation
    '''
    def generateRotation(self, config, command, angle, feed_rate):
        # - Create position
        position = self.generateRotationPosition(config, angle)

        # - Create GCODE
        return command.replace("{Position}", str(position)).replace("{FeedRate}", str(float(feed_rate) * 60)) + "\r\n"

    '''
    Generate wire enable command
    '''
    def generateWireEnable(self, config, power):
        return config.WireOnCommand.replace("{WirePower}", "%.2f" % float(power)) + "\r\n"

    '''
    Generate wire disable command
    '''
    def generateWireDisable(self, config):
        return config.WireOffCommand + "\r\n"

    '''
    Generate command for compensated power
    '''
    def generateWireCompensatedPower(self, config, wire_length):
        min_power   = float(config.WireMinPower)
        max_power   = float(config.WireMaxPower)
        min_length  = float(config.FieldWidth)

        # - Calculate power
        power = (min_power * wire_length) / min_length

        # - Clip power
        if power > max_power:
            power = max_power

        return power
        
    def generateStartBlock(self, config, start_point):
        GCODE = ";*** FOAM BLOCK ***\r\n"

        GCODE += ";Width: {}\r\n".format(config.BlockWidth)
        GCODE += ";Length: {}\r\n".format(config.BlockLength)
        GCODE += ";Height: {}\r\n".format(config.BlockHeight)

        GCODE += ";Position - Left-Bottom-Front corner\r\n"
        GCODE += ";Position.X: {}\r\n".format(config.BlockPosition.x)
        GCODE += ";Position.Y: {}\r\n".format(config.BlockPosition.y)
        GCODE += ";Position.Z: {}\r\n".format(config.BlockPosition.z)
        
        GCODE += "; *** START BLOCK ***\r\n"

        if config.EnableHoming:
            # - Homing
            GCODE += config.HomingCommand + "\r\n"

            initPosCommand = self.generateTravelPosition(config,
                config.HomingX1, config.HomingZ1, config.HomingX2, config.HomingZ2
                )
            
            if config.FiveAxisMachine:
                initPosCommand += " " + self.generateRotationPosition(config, config.HomingR1 )

            # - Initialize position
            GCODE += config.InitPositionCommand.replace("{Position}", initPosCommand ) + "\r\n"

        if config.EnableParking:
            # - Park
            GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
               config.ParkX, config.ParkZ, config.ParkX, config.ParkZ )
            if config.FiveAxisMachine:
                GCODE += self.generateRotation(config, config.MoveCommand, config.ParkR1, config.FeedRateRotate)

        # - Go to start point on parking Z if parking enabled
        if start_point is not None:
            start_L, start_R = start_point
            if config.EnableParking:
                GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
                start_L.y, config.ParkZ, start_R.y, config.ParkZ)

        wirePower = config.WireMinPower
        # - generate compensated wire power
        if config.DynamicWirePower:
            # - Calculate wire length
            wire_length = start_L.distanceToPoint(start_R)
            wirePower = self.generateWireCompensatedPower(config, wire_length)

        # - Enable wire
        GCODE += self.generateWireEnable(config, wirePower)

        return GCODE

    def generateEndBlock(self, config):
        GCODE = "; *** END BLOCK ***\r\n"

        # - Up wire at current position to park height
        if config.EnableParking:
            up_posistion  = "%s%.2f %s%.2f" % (config.Z1AxisName, config.ParkZ, config.Z2AxisName, config.ParkZ)
            feed_rate     = config.FeedRateMove
            GCODE += config.MoveCommand.replace("{Position}", up_posistion).replace("{FeedRate}", str(float(feed_rate) * 60)) + "\r\n"

        # - Disable wire
        GCODE += self.generateWireDisable(config)

        # - Park XZ
        if config.EnableParking:
            GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
                config.ParkX, config.ParkZ, config.ParkX, config.ParkZ )
            # - Park R1
            if config.FiveAxisMachine:
                GCODE += self.generateRotation(config, config.MoveCommand, config.ParkR1, config.FeedRateRotate)
        return GCODE

    '''
    Make GCODE from rotation element
    '''
    def makeGCODEFromRotation(self, rt, config):
        GCODE = ["; - Rotation [%s] -\r\n" % rt.Label]

        # - Generate rotation command
        GCODE.append(self.generateRotation(config, config.MoveCommand, rt.Angle, config.FeedRateRotate))
        return GCODE

    '''
    Calculate dynamic power if needed and return gcode for command
    '''
    def getDynamicWirePowerCommand(self, point1, point2, config):
        wirePowerCommand = ""
        # - generate compensated wire power
        if config.DynamicWirePower:
            # - Calculate wire length
            wire_length = point1.distanceToPoint(point2);
            wirePowerCommand = "S%.2f" % (self.generateWireCompensatedPower(config, wire_length))
        return wirePowerCommand
    
    '''
    Generate GCODE from route
    '''
    def makeGCODE(self, route_list, config):
        
        # - Task GCODE buffer
        TASK = [";\r\n", "; *** TASK BLOCK ***\r\n"]
        start_point = None
        # - Wal all routes
        for route in route_list:
            TASK += [";\r\n", "; --- Route begin [%s] ---\r\n" % route.Label]

            point_index = 0

            # - Store first point as start point
            if start_point is None: 
                start_point = (route.Offset_L[0], route.Offset_R[0])

            for i in range(len(route.Data)):                                
                # - Access item
                object_index = route.Data[i]

                object = route.Objects[object_index]

                if object.Type == "Rotation": # - Make GCODE from rotation
                    TASK += self.makeGCODEFromRotation(object, config)
                else:
                    addPause = object.AddPause if hasattr(object, "AddPause") else False
                    duration = object.PauseDuration if hasattr(object, "PauseDuration") else 0

                    TASK += ["; - %s [%s]\r\n" % (object.Type, object.Label)]

                    points_count = object.PointsCount if i == 0 else object.PointsCount - 1
                    # - Step over each point
                    for _ in range(points_count):
                        point_l = route.Offset_L[point_index]
                        point_r = route.Offset_R[point_index]

                        wirePowerCommand = self.getDynamicWirePowerCommand(point_l, point_r, config)
                        
                        # - Generate CUT travel command
                        TASK += self.generateTravel(config, config.CutCommand, config.FeedRateCut, wirePowerCommand,
                        point_l.y, point_l.z, point_r.y, point_r.z, )

                        # - Increase point index
                        point_index += 1
                    
                    if addPause and duration > 0:
                        if config.TimeUnits == 1: #["Seconds", "Milliseconds"]
                            duration = duration * 1000
                        TASK += self.generatePause(config.PauseCommand, duration)
               

            TASK += ["; --- Route end [%s] ---\r\n" % route.Label, ";\r\n"]

        # ---- Generate startup block
        START = self.generateStartBlock(config, start_point)        
        END   = self.generateEndBlock(config)

        program = START + ''.join(TASK) + END

        print ("GCODE generated")

        dialog = QtGui.QFileDialog()
        lastDir = dialog.directory().absolutePath()
        # - Open save file dialog
        save_path, save_filter = dialog.getSaveFileName(None, "Save GCODE", os.path.join(lastDir, route_list[0].Label), "*.gcode") # PySide

        # - Check path
        if save_path == "":
            print ("GCODE saving aborted (no output file path specified)")
        else:
            try:
                with open(save_path, "w") as f:
                    f.write(program)
                print ("GCODE saved into [%s]" % save_path)
            except Exception:
                App.Console.PrintError("Unable to save GCODE in [" + save_path + "]\n")

    def GetResources(self):
        return {"Pixmap"  : utilities.getIconPath("gcode.svg"), # the name of a svg file available in the resources
                'Accel' : "", # a default shortcut (optional)
                "MenuText": "Generate GCODE file",
                "ToolTip" : "Generate GCODE file from selected route"}

    def Activated(self):
        # - Get selecttion
        routes = [item.Object for item in Gui.Selection.getSelectionEx()]
        
        job_name = routes[0].JobName

        group = FreeCAD.ActiveDocument.getObject(job_name)
        if group is None:
            QtGui.QMessageBox.critical(None, "Job not found.", "Job [{}] not found in active document.".format(job_name))
            return
        
        # - Get CNC configuration
        config = FreeCAD.ActiveDocument.getObject(group.ConfigName)

        # - Check routes type
        for route in routes:
            if not hasattr(route, "Type") or (route.Type != "Route"):
                QtGui.QMessageBox.critical(None, "Error generating Gcode", "Object type not supported. Check Selected objects.")
        
        hasError = False
        for route in routes:
            if route.Error is not None and len(route.Error) > 0:
                print(route.Error)
                hasError = True
                break

        if hasError:
            QtGui.QMessageBox.critical(None, "Error generating Gcode", "Route data is incorrect. Check Selected routes.")
        else:
            self.makeGCODE(routes, config)

        App.ActiveDocument.recompute()
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            # - Get selecttion
            routes = [item.Object for item in Gui.Selection.getSelectionEx()]

            # - nothing selected
            if len(routes) == 0:
                return False
            
            # - Check types
            for route in routes:
                if not hasattr(route, "Type") or (route.Type != "Route"):
                    return False
                
            job_name = routes[0].JobName
            for  route in routes:
                if route.JobName != job_name:
                    return False
                
            return True
            
Gui.addCommand("MakeGcode", Postprocess())
