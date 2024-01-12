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
import utilities


class Postprocess():
    """Make Gcode"""

    '''
    Generate position string for travel
    '''
    def generateTravelPosition(self, config, X1, Z1, X2, Z2):
        return "%s%.2f %s%.2f %s%.2f %s%.2f" % (
            config.X1AxisName, float(X1),
            config.Z1AxisName, float(Z1),
            config.X2AxisName, float(X2),
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
    def generateTravel(self, config, command, feed_rate, X1, Z1, X2, Z2):
        # - Create position
        position = self.generateTravelPosition(config, X1, Z1, X2, Z2)

        # - Create GCODE
        return command.replace("{Position}", str(position)).replace("{FeedRate}", str(float(feed_rate) * 60)) + "\r\n"

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

        # - Generate command
        return self.generateWireEnable(config, power)
    
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

            # - Calculate wire length
            wire_length = path.Path_L[index].distanceToPoint(path.Path_R[index]);

            # - Insert compensated wire power
            #GCODE.append(generateWireCompensatedPower(config, wire_length))

            # - Generate CUT travel command
            GCODE.append(self.generateTravel(config, config.CutCommand, config.FeedRateCut,
            path.Path_L[index].y, path.Path_L[index].z,
            path.Path_R[index].y, path.Path_R[index].z,
            ))

            # - Store start point
            if out_start is None: out_start = (path.Path_L[index], path.Path_R[index])

            # - Update end point
            out_end = (path.Path_L[index], path.Path_R[index])

        return (out_start, out_end, GCODE)

    def generateStartBlock(self, config, start_point):
        GCODE = "; *** START BLOCK ***\r\n"

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
        GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove,
            config.ParkX, config.ParkZ, config.ParkX, config.ParkZ
            )
        GCODE += self.generateRotation(config, config.MoveCommand, config.ParkR1, config.FeedRateRotate)

        # - Go to start point on parking Z
        if start_point is not None:
            start_L, start_R = start_point
            GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove,
            start_L.y, config.ParkZ, start_R.y, config.ParkZ
            )

        # - Enable wire
        GCODE += self.generateWireEnable(config, config.WireMinPower)

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
        GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove,
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


    def makeGCODEFromEnter(self, enter, config):
        GCODE = ["; - Enter: [%s]\r\n" % enter.Label]

        # - Move to entry point
        GCODE += self.generateTravel(config, config.MoveCommand, config.FeedRateMove,
            enter.PointXL, enter.SafeHeight, enter.PointXR, enter.SafeHeight
        )

        # - Generate enter
        GCODE += self.generateTravel(config, config.CutCommand, config.FeedRateCut,
            enter.PointXL, enter.PointZL, enter.PointXR, enter.PointZR
        )

        return GCODE

    def makeGCODEFromExit(self, exit, config):
        GCODE = ["; - Exit [%s]\r\n" % exit.Label]

        # - Generate exit
        GCODE += self.generateTravel(config, config.CutCommand, config.FeedRateCut,
            exit.PointXL, exit.SafeHeight, exit.PointXR, exit.SafeHeight
        )

        return GCODE

    def makeGCODEFromMove(self, move, reversed, config):
        GCODE = ["; - Move [%s] :: %s\r\n" % (move.Label, "S < E" if reversed else "S > E")]

        # - Detect directed offset
        if reversed:
            # - Move from end to start
            GCODE += self.generateTravel(config, config.CutCommand, move.FeedRate,
                move.PointXL, move.PointZL, move.PointXR, move.PointZR
            )
        else:
            # - Move from start to end
            GCODE += self.generateTravel(config, config.CutCommand, move.FeedRate,
                move.PointXL + float(move.InXDirection), move.PointZL + float(move.InZDirection), move.PointXR + float(move.InXDirection), move.PointZR + float(move.InZDirection)
            )

        return GCODE
    
    def makeGCODEFromJoin(self, move, reversed, config):
        GCODE = ["; - Join [%s] :: %s\r\n" % (move.Label, "S < E" if reversed else "S > E")]

        # - Detect directed offset
        if reversed:
            # - Move from end to start
            GCODE += self.generateTravel(config, config.CutCommand, move.FeedRate,
                move.PointXLA, move.PointZLA, move.PointXRA, move.PointZRA
            )
        else:
            # - Move from start to end
            GCODE += self.generateTravel(config, config.CutCommand, move.FeedRate,
                move.PointXLB, move.PointZLB, move.PointXRB, move.PointZRB
            )

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

        operationsCount = 2 # - taking into account start and end blocks
        operationsDone = 0

        # - calculate motions count
        for route in route_list:
            operationsCount += len(route.Data)

        progress = PySide.QtGui.QProgressDialog("Generating GCode", "Cancel", 0, operationsCount)
        progress.setWindowModality(PySide.QtGui.Qt.WindowModal)

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
                if progress.wasCanceled():
                    msgBox = PySide.QtGui.QMessageBox()
                    msgBox.setText("Operation was canceled by user.")
                    msgBox.exec_()
                    return
                
                # - Access item
                item = route.Data[i]

                # - This is a Path
                if item.Object.Type == "Path":
                    # - Remove last point from task as it must be same point as new path start
                    if prev_path:
                        del TASK[-1]

                    # - Make GCODE from path
                    (start, end, text) = self.makeGCODEFromPath(item.Object, item.Reversed, config)
                    TASK += text

                    # - Store first point as start point
                    if start_point is None: start_point = start

                    # - Update end point
                    end_point = end

                    # - Update prev element type
                    prev_path = True

                elif item.Object.Type == "Move":
                    # - Make GCODE from move
                    TASK += self.makeGCODEFromMove(item.Object, item.Reversed, config)

                # - This is a Rotation
                elif item.Object.Type == "Rotation":
                    # - Make GCODE from rotation
                    TASK += self.makeGCODEFromRotation(item.Object, config)
                    prev_path = False

                elif item.Object.Type == "Enter":
                    TASK += self.makeGCODEFromEnter(item.Object, config)

                elif item.Object.Type == "Exit":
                    TASK += self.makeGCODEFromExit(item.Object, config)

                elif item.Object.Type == "Join":
                    TASK += self.makeGCODEFromJoin(item.Object, item.Reversed, config)
                
                operationsDone += 1
                progress.setValue(operationsDone)

            TASK += ["; --- Route end [%s] ---\r\n" % route.Label, ";\r\n"]

        # ---- Generate startup block
        START = self.generateStartBlock(config, start_point)
        operationsDone += 1
        progress.setValue(operationsDone)
        END   = self.generateEndBlock(config, end_point)

        progress.setValue(operationsCount)

        program = START + ''.join(TASK) + END

        print ("GCODE generated")

        #print (program)
        # - Open save file dialog
        try:
            save_path = PySide.QtGui.QFileDialog.getSaveFileName(None, QString.fromLocal8Bit("Save GCODE"), "", "*.gcode") # PyQt4
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
        # - Get CNC configuration
        config = FreeCAD.activeDocument().getObjectsByLabel('Config')[0]

         # - Get selecttion
        routes = [item.Object for item in Gui.Selection.getSelectionEx()]

        for route in routes:
            print("Initial route Data:")
            print(route.Data)
            route.touch()
            route.recompute()
            print("Recomputed route Data:")
            print(route.Data)

        self.makeGCODE(routes, config)
    
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
            return True
            
Gui.addCommand("MakeGcode", Postprocess())
