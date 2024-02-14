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
import PySide
from PySide import QtCore
from PySide import QtGui
import utilities


class Postprocess():
    """Make Gcode"""

    '''
    Generate position string for travel
    '''
    def generateTravelPosition(self, config, X1, Z1, X2, Z2):
        return "%s%.2f %s%.2f %s%.2f %s%.2f" % (
            config.X1AxisName, float(X1 - config.OriginX),
            config.Z1AxisName, float(Z1),
            config.X2AxisName, float(X2 - config.OriginX),
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
        GCODE = "; *** START BLOCK ***\r\n"

        if config.EnableHoming:
            # - Homing
            GCODE += config.HomingCommand + "\r\n"

            # - Initizlie position
            GCODE += config.InitPositionCommand.replace("{Position}",
                self.generateTravelPosition(config,
                config.HomingX1, config.HomingZ1, config.HomingX2, config.HomingZ2
                ) + " " +
                self.generateRotationPosition(config,
                config.HomingR1
                )
            ) + "\r\n"

        # - Park
        GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
            config.ParkX, config.ParkZ, config.ParkX, config.ParkZ
            )
        GCODE += self.generateRotation(config, config.MoveCommand, config.ParkR1, config.FeedRateRotate)

        # - Go to start point on parking Z
        if start_point is not None:
            start_L, start_R = start_point
            GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
            start_L.y, config.ParkZ, start_R.y, config.ParkZ
            )

        wirePower = config.WireMinPower
        # - generate compensated wire power
        if config.DynamicWirePower:
            # - Calculate wire length
            wire_length = start_L.distanceToPoint(start_R);
            wirePower = self.generateWireCompensatedPower(config, wire_length)

        # - Enable wire
        GCODE += self.generateWireEnable(config, wirePower)

        return GCODE

    def generateEndBlock(self, config, end_point):
        GCODE = "; *** END BLOCK ***\r\n"

        # - Up wire at current position to park height
        #up_posistion  = "%s%.2f %s%.2f" % (config.Z1AxisName, config.ParkZ, config.Z2AxisName, config.ParkZ)
        #feed_rate     = config.FeedRateMove
        #GCODE += config.MoveCommand.replace("{Position}", up_posistion).replace("{FeedRate}", str(float(feed_rate) * 60)) + "\r\n"

        # - Disable wire
        GCODE += self.generateWireDisable(config)

        # - Park XZ
        GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
            config.ParkX, config.ParkZ, config.ParkX, config.ParkZ
            )

        # - Park R1
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
    Make GCODE from enter element
    '''
    def makeGCODEFromEnter(self, enter, reversed, config):
        GCODE = ["; - Enter: [%s]\r\n" % enter.Label]

        # out_start = None
        # out_end   = None

        # - Step over each point
        for i in range(enter.PointsCount):
            # - Get point index
            index = enter.PointsCount - i - 1 if reversed else i

            # - Move to entry point
            if i == 0:
                GCODE.append(self.generateTravel(config, config.MoveCommand, config.FeedRateMove, "",
                    enter.Path_L[index].y, enter.SafeHeight, enter.Path_R[index].y, enter.SafeHeight))
                
            wirePowerCommand = ""
            # - generate compensated wire power
            if config.DynamicWirePower:
                # - Calculate wire length
                wire_length = enter.Path_L[index].distanceToPoint(enter.Path_R[index]);
                wirePowerCommand = "S%.2f" % (self.generateWireCompensatedPower(config, wire_length))

            # - Generate CUT travel command
            GCODE.append(self.generateTravel(config, config.CutCommand, config.FeedRateCut, wirePowerCommand,
            enter.Path_L[index].y, enter.Path_L[index].z,
            enter.Path_R[index].y, enter.Path_R[index].z,
            ))

        if enter.AddPause:
            GCODE.append(self.generatePause(config.PauseCommand, enter.PauseDuration))

            # # - Store start point
            # if out_start is None: out_start = (enter.Path_L[index], enter.Path_R[index])

            # # - Update end point
            # out_end = (enter.Path_L[index], enter.Path_R[index])

        return GCODE

    '''
    Make GCODE from exit element
    '''
    def makeGCODEFromExit(self, exit, config):
        GCODE = ["; - Exit [%s]\r\n" % exit.Label]

         # - Step over each point
        for i in range(exit.PointsCount):
            # - Get point index
            index = exit.PointsCount - i - 1 if reversed else i
                
            wirePowerCommand = ""
            # - generate compensated wire power
            if config.DynamicWirePower:
                # - Calculate wire length
                wire_length = exit.Path_L[index].distanceToPoint(exit.Path_R[index]);
                wirePowerCommand = "S%.2f" % (self.generateWireCompensatedPower(config, wire_length))

            # - Generate CUT travel command
            GCODE.append(self.generateTravel(config, config.CutCommand, config.FeedRateCut, wirePowerCommand,
            exit.Path_L[index].y, exit.Path_L[index].z,
            exit.Path_R[index].y, exit.Path_R[index].z,
            ))

        
        if exit.AddPause:
            GCODE.append(self.generatePause(config.PauseCommand, exit.PauseDuration))

        return GCODE

    '''
    Make GCODE from path element
    '''
    def makeGCODEFromPath(self, path, reversed, config):
        GCODE     = ["; - Path [%s]\r\n" % path.Label]
        out_start = None
        out_end   = None

        # - Step over each point
        for i in range(path.PointsCount):
            # - Get point index
            index = path.PointsCount - i - 1 if reversed else i

            wirePowerCommand = ""
            # - generate compensated wire power
            if config.DynamicWirePower:
                # - Calculate wire length
                wire_length = path.Path_L[index].distanceToPoint(path.Path_R[index]);
                wirePowerCommand = "S%.2f" % (self.generateWireCompensatedPower(config, wire_length))

            # - Generate CUT travel command
            GCODE.append(self.generateTravel(config, config.CutCommand, config.FeedRateCut, wirePowerCommand,
            path.Path_L[index].y, path.Path_L[index].z,
            path.Path_R[index].y, path.Path_R[index].z,
            ))

            # - Store start point
            if out_start is None: out_start = (path.Path_L[index], path.Path_R[index])

            # - Update end point
            out_end = (path.Path_L[index], path.Path_R[index])

        if path.AddPause:
            GCODE.append(self.generatePause(config.PauseCommand, path.PauseDuration))

        return (out_start, out_end, GCODE)

    '''
    Make GCODE from move element
    '''
    def makeGCODEFromMove(self, move, reversed, config):
        GCODE = ["; - Move [%s] :: %s\r\n" % (move.Label, "S < E" if reversed else "S > E")]

        # - Step over each point
        for i in range(move.PointsCount):
            # - Get point index
            index = move.PointsCount - i - 1 if reversed else i

            wirePowerCommand = ""
            # - generate compensated wire power
            if config.DynamicWirePower:
                # - Calculate wire length
                wire_length = move.Path_L[index].distanceToPoint(move.Path_R[index]);
                wirePowerCommand = "S%.2f" % (self.generateWireCompensatedPower(config, wire_length))

            # - Generate CUT travel command
            GCODE.append(self.generateTravel(config, config.CutCommand, config.FeedRateCut, wirePowerCommand,
            move.Path_L[index].y, move.Path_L[index].z,
            move.Path_R[index].y, move.Path_R[index].z,
            ))

        if move.AddPause:
            GCODE.append(self.generatePause(config.PauseCommand, move.PauseDuration))

        return GCODE
    
    '''
    Make GCODE from join element
    '''
    def makeGCODEFromJoin(self, move, reversed, config):
        GCODE = ["; - Join [%s] :: %s\r\n" % (move.Label, "S < E" if reversed else "S > E")]

        # - Detect directed offset
        if reversed:
            # - Move from end to start
            GCODE += self.generateTravel(config, config.CutCommand, move.FeedRate, "",
                move.PointXLA, move.PointZLA, move.PointXRA, move.PointZRA
            )
        else:
            # - Move from start to end
            GCODE += self.generateTravel(config, config.CutCommand, move.FeedRate, "", 
                move.PointXLB, move.PointZLB, move.PointXRB, move.PointZRB
            )
        
        if move.AddPause:
            GCODE.append(self.generatePause(config.PauseCommand, move.PauseDuration))

        return GCODE

    '''
    Generate GCODE from route
    '''
    def makeGCODE(self, route_list, config):
        # - Check routes type
        for route in route_list:
            if not hasattr(route, "Type") or (route.Type != "Route"):
                print ("ERROR: Not supported input")
                return

        start_point = None
        end_point   = None

        # - Task GCODE buffer
        TASK = [";\r\n", "; *** TASK BLOCK ***\r\n"]

        # - Wal all routes
        for route in route_list:
            TASK += [";\r\n", "; --- Route begin [%s] ---\r\n" % route.Label]

            # - Walk throug all route elemets
            prev_path = False
            for i in range(len(route.Data)):                                
                # - Access item
                item = route.Data[i]

                object = route.Objects[item]
                reversed = route.DataDirection[i]

                # - This is a Path
                if object.Type == "Path" or object.Type == "Projection":
                    # - Remove last point from task as it must be same point as new path start
                    if prev_path:
                        del TASK[-1]

                    # - Make GCODE from path
                    (start, end, text) = self.makeGCODEFromPath(object, reversed, config)
                    TASK += text

                    # - Store first point as start point
                    if start_point is None: start_point = start

                    # - Update end point
                    end_point = end

                    # - Update prev element type
                    prev_path = True

                elif object.Type == "Move":
                    # - Make GCODE from move
                    TASK += self.makeGCODEFromMove(object, reversed, config)

                # - This is a Rotation
                elif object.Type == "Rotation":
                    # - Make GCODE from rotation
                    TASK += self.makeGCODEFromRotation(object, config)
                    prev_path = False

                elif object.Type == "Enter":
                    TASK += self.makeGCODEFromEnter(object, reversed, config)

                elif object.Type == "Exit":
                    TASK += self.makeGCODEFromExit(object, config)

                elif object.Type == "Join":
                    TASK += self.makeGCODEFromJoin(object, reversed, config)
                

            TASK += ["; --- Route end [%s] ---\r\n" % route.Label, ";\r\n"]

        # ---- Generate startup block
        START = self.generateStartBlock(config, start_point)        
        END   = self.generateEndBlock(config, end_point)

        program = START + ''.join(TASK) + END

        print ("GCODE generated")

        # - Open save file dialog
        try:
            save_path = QFileDialog.getSaveFileName(None, QString.fromLocal8Bit("Save GCODE"), "", "*.gcode") # PyQt4
        except Exception:
            save_path, save_filter = PySide.QtGui.QFileDialog.getSaveFileName(None, "Save GCODE", "", "*.gcode") # PySide

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
        group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
        if group is not None and group.Type == "Job":     
            # - Get CNC configuration
            config = FreeCAD.ActiveDocument.getObject(group.ConfigName)

            # - Get selecttion
            routes = [item.Object for item in Gui.Selection.getSelectionEx()]
            
            hasError = False
            for route in routes:
                route.touch()
                route.recompute()
                if route.Error is not None and len(route.Error) > 0:
                    print(route.Error)
                    hasError = True
                    break

            if hasError:
                PySide.QtGui.QMessageBox.critical(None, "Error generating Gcode", "Route data is incorrect. Check Selected routes.")
            else:
                self.makeGCODE(routes, config)

            App.ActiveDocument.recompute()
    
    def IsActive(self):
        if FreeCAD.ActiveDocument is None:
            return False
        else:
            group = Gui.ActiveDocument.ActiveView.getActiveObject("group")
            if group is not None and group.Type == "Job":
                # - Get selecttion
                routes = [item.Object for item in Gui.Selection.getSelectionEx()]

                # - nothing selected
                if len(routes) == 0:
                    return False
                
                # - Check types
                for route in routes:
                    if not hasattr(route, "Type") or (route.Type != "Route"):
                        return False
                return True
            return False
            
Gui.addCommand("MakeGcode", Postprocess())
