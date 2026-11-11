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
import math

ROUTE_TYPES = ("Route", "RouteClone")

class Postprocess():
    """Make Gcode"""

    '''
    Format expected run time given in seconds as HH:MM:SS
    '''
    def formatRunTime(self, seconds):
        total = int(round(max(0.0, float(seconds))))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return "%02d:%02d:%02d" % (hours, minutes, secs)

    '''
    Accumulate expected motion time (seconds) for a move.
    
    Feed rates in the machine configuration are stored in mm/s, so the move
    time is distance / feed rate regardless of the emitted feed rate mode.
    '''
    def _addMoveTime(self, feed_rate, distance):
        try:
            rate = float(feed_rate)
            length = float(distance)
        except (TypeError, ValueError):
            return
        if rate <= 0.0 or length < 0.0:
            return
        self._run_time_seconds = getattr(self, "_run_time_seconds", 0.0) + length / rate

    '''
    Accumulate expected travel time (seconds) for a move.

    G93: the postprocessor emits F = 60 * feed_rate / L, where L is the
    longer wire-end travel. The move therefore takes L / feed_rate.
    G94: F is a path feed rate, so the length is the Euclidean length of the
    commanded axis vector (X1, Z1, X2, Z2), as controllers such as GRBL
    compute it. This is not the longer wire end: two ends moving 10 mm each
    produce 14.14 mm of programmed path, not 10 mm.
    Rapids are G0 moves; controllers derive their speed from the axis rapid
    rates, so their time is set by the slowest axis, not by F.

    Moves from an unknown position (no homing and no parking) cannot be
    estimated and are skipped.
    '''
    def _addTravelTime(self, config, feed_rate, X1, Z1, X2, Z2, rapid=False):
        current_L = getattr(self, "_current_L", None)
        current_R = getattr(self, "_current_R", None)
        if current_L is None or current_R is None:
            return

        dX1 = float(X1) - current_L[0]
        dZ1 = float(Z1) - current_L[1]
        dX2 = float(X2) - current_R[0]
        dZ2 = float(Z2) - current_R[1]

        if rapid:
            # - G0: the slowest axis sets the pace
            distance = max(abs(dX1), abs(dZ1), abs(dX2), abs(dZ2))
        elif config.FeedRateMode == utilities.FC_FEED_RATE_MODES[1]: # G93
            distance = max(math.hypot(dX1, dZ1), math.hypot(dX2, dZ2))
        else: # G94
            distance = math.sqrt(dX1 * dX1 + dZ1 * dZ1 + dX2 * dX2 + dZ2 * dZ2)

        self._addMoveTime(feed_rate, distance)

    '''
    Accumulate expected pause time (seconds)
    '''
    def _addPauseTime(self, duration):
        try:
            pause = float(duration)
        except (TypeError, ValueError):
            return
        if pause > 0.0:
            self._run_time_seconds = getattr(self, "_run_time_seconds", 0.0) + pause

    '''
    Makes commented line 
    '''
    def makeCommentedLine(self, config, inputString):
        if config.CommentStyle == utilities.FC_COMMENT_STYLES[0]: # inline comments started with ;
            return "; {}".format(inputString)
        elif config.CommentStyle == utilities.FC_COMMENT_STYLES[1]: # inline or multiline comment inside ()
            return "({})".format(inputString)
        else:
            return ""

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
    
    @param angle - incremental rotation angle to add to the current rotation position.
    
    @return absolute rotation position command.
    
    Rotation angles are incremental: each rotation turns the axis from its current position.
    rotation_position accumulates them into the absolute coordinate emitted in the GCODE
    (the output is in absolute coordinates, see G90 in the start block).
    '''
    def generateRotationPosition(self, config, angle):
        self.rotation_position += float(angle)

        return "%s%.2f" % (
            config.R1AxisName, self.rotation_position
        )

    '''
    Update tracked wire position (raw coordinate pairs: (X1,Z1) and (X2,Z2))
    '''
    def _setCurrent(self, X1, Z1, X2, Z2):
        self._current_L = (float(X1), float(Z1))
        self._current_R = (float(X2), float(Z2))

    '''
    Calculate feed rate value for a move.
    
    G94: feed = feed_rate * 60 (mm/min).
    G93: feed = feed_rate * 60 / L, where L is the longer wire-end travel distance.
    Degenerate move (L <= epsilon) falls back to feed_rate * 60 (G93 requires F on every G1 line).
    '''
    def _calculateFeed(self, config, feed_rate, X1, Z1, X2, Z2):
        feed = float(feed_rate) * 60
        if self._g93_emitted and self._current_L is not None and self._current_R is not None:
            L = max(
                math.hypot(float(X1) - self._current_L[0], float(Z1) - self._current_L[1]),
                math.hypot(float(X2) - self._current_R[0], float(Z2) - self._current_R[1])
            )
            if L > 1e-6:
                feed = feed / L
        return feed

    '''
    Format feed rate token for a move (number only; template supplies the literal F)
    '''
    def _formatFeed(self, config, feed_rate, X1, Z1, X2, Z2):
        return "%.2f" % self._calculateFeed(config, feed_rate, X1, Z1, X2, Z2)

    '''
    Generate travel
    '''
    def generateTravel(self, config, command, feed_rate, wire_power, X1, Z1, X2, Z2, rapid=False):
        # - Create position
        position = self.generateTravelPosition(config, X1, Z1, X2, Z2)

        # - Calculate feed (mode-aware) and track the new position/time
        feed = self._formatFeed(config, feed_rate, X1, Z1, X2, Z2)
        self._addTravelTime(config, feed_rate, X1, Z1, X2, Z2, rapid)
        self._setCurrent(X1, Z1, X2, Z2)

        # - Create GCODE
        return command.replace("{Position}", str(position)).replace("{FeedRate}", feed).replace("{WirePower}", str(wire_power)) + "\n"

    '''
    Generate rapid travel
    '''
    def generateRapidTravel(self, config, X1, Z1, X2, Z2):        
        # - Create GCODE
        return self.generateTravel(config, config.MoveCommand, config.FeedRateMove, '', X1, Z1, X2, Z2, True)

    '''
    Generate pause
    '''
    def generatePause(self, command, duration):
        return command.replace("{Duration}", "%.2f" %  float(duration)) + "\n"

    '''
    Generate rotation
    '''
    def generateRotation(self, config, command, angle, feed_rate):
        # - Create position
        position = self.generateRotationPosition(config, angle)

        # - Calculate feed (mode-aware). Rotation does not change the wire (y,z)
        #   position, so _current_L/_current_R are not updated.
        feed = float(feed_rate) * 60
        if self._g93_emitted:
            delta = abs(float(angle))
            if delta > 1e-6:
                feed = feed / delta

        # - Track rotation time. A rotation is emitted on its own line, so the
        #   angle is the only moving axis: G94 and G93 both take angle / feed_rate.
        self._addMoveTime(feed_rate, abs(float(angle)))

        # - Create GCODE
        return command.replace("{Position}", str(position)).replace("{FeedRate}", "%.2f" % feed) + "\n"

    '''
    Generate wire enable command
    '''
    def generateWireEnable(self, config, power):
        return config.WireOnCommand.replace("{WirePower}", "%.2f" % float(power)) + "\n"

    '''
    Generate wire disable command
    '''
    def generateWireDisable(self, config):
        return config.WireOffCommand + "\n"

    '''
    Generate command for compensated power
    '''
    # pending removal
    def generateWireCompensatedPower(self, config, wire_length, min_power):
        max_power   = float(config.WireMaxPower)
        min_length  = float(config.FieldWidth)

        # - Calculate power
        power = (min_power * wire_length) / min_length

        # - Clip power
        if power > max_power:
            power = max_power

        return power
        
    def generateStartBlock(self, config, start_point):
        GCODE = ""
        self.rotation_position = 0.0
        self._current_L = None
        self._current_R = None
        self._run_time_seconds = 0.0
        self._g93_emitted = False

        if config.StartProgramCode:
            GCODE += "{}\n".format(config.StartProgramCode)
            GCODE += "\n"

        GCODE += self.makeCommentedLine(config, "*** PROGRAM ***") + "\n"
        GCODE += self.makeCommentedLine(config, "Expected run time: {ExpectedRunTime}") + "\n"
        GCODE += "\n"

        GCODE += self.makeCommentedLine(config, "*** MACHINE ***") + "\n"
        GCODE += self.makeCommentedLine(config, "Machine type: {}".format("5-Axis" if config.FiveAxisMachine else "4-Axis")) + "\n"
        GCODE += self.makeCommentedLine(config, "Width: {}".format(config.FieldWidth)) + "\n"
        GCODE += self.makeCommentedLine(config, "Length: {}".format(config.HorizontalTravel)) + "\n"
        GCODE += self.makeCommentedLine(config, "Height: {}".format(config.VerticalTravel)) + "\n"
        GCODE += "\n"

        GCODE += self.makeCommentedLine(config, "*** FOAM BLOCK ***") + "\n"

        GCODE += self.makeCommentedLine(config, "Width: {}".format(config.BlockWidth)) + "\n"
        GCODE += self.makeCommentedLine(config, "Length: {}".format(config.BlockLength)) + "\n"
        GCODE += self.makeCommentedLine(config, "Height: {}".format(config.BlockHeight)) + "\n"

        GCODE += self.makeCommentedLine(config, "Position - Left-Bottom-Front corner in relation to the origin") + "\n"
        GCODE += self.makeCommentedLine(config, "Position.X: {}".format(config.BlockPosition.x)) + "\n"
        GCODE += self.makeCommentedLine(config, "Position.Y: {}".format(config.BlockPosition.y)) + "\n"
        GCODE += self.makeCommentedLine(config, "Position.Z: {}".format(config.BlockPosition.z)) + "\n"
        
        GCODE += "\n"
        GCODE += self.makeCommentedLine(config, "*** START BLOCK ***") + "\n"

        GCODE += self.makeCommentedLine(config, "Set units to millimeters") + "\n"
        GCODE += "G21\n"
        GCODE += self.makeCommentedLine(config, "Set absolute positioning") + "\n"
        GCODE += "G90\n"
        GCODE += self.makeCommentedLine(config, "Set G94 feed rate mode") + "\n"
        GCODE += "G94\n"

        if config.EnableHoming:
            # - Homing
            GCODE += self.makeCommentedLine(config, "- Homing -") + "\n"
            GCODE += config.HomingCommand + "\n"

            initPosCommand = self.generateTravelPosition(config,
                config.HomingX1, config.HomingZ1, config.HomingX2, config.HomingZ2
                )
            
            if config.FiveAxisMachine:
                initPosCommand += " " + self.generateRotationPosition(config, config.HomingR1)

            # - Initialize position
            GCODE += config.InitPositionCommand.replace("{Position}", initPosCommand ) + "\n"
            # - After $H + G92 all axes are at their max position (debounce offset),
            #   declared as the homing coordinates -> position is now known.
            self._setCurrent(config.HomingX1, config.HomingZ1, config.HomingX2, config.HomingZ2)

        if config.EnableParking:
            # - Park
            GCODE += self.makeCommentedLine(config, "- Parking -") + "\n"
            GCODE += self.generateRapidTravel(config, config.ParkX, config.ParkZ, config.ParkX, config.ParkZ )
            if config.FiveAxisMachine:
                GCODE += self.generateRotation(config, config.MoveCommand, config.ParkR1, config.FeedRateRotate)

        # - Go to start point on parking Z if parking enabled
        if start_point is not None:
            start_L, start_R = start_point
            if config.EnableParking:
                GCODE += self.generateRapidTravel(config, start_L.y, config.ParkZ, start_R.y, config.ParkZ)

        wirePower = config.WireMinPower
        # - generate compensated wire power
        # pending removal
        if config.DynamicWirePower and start_point is not None:
            # - Calculate wire length
            wire_length = start_L.distanceToPoint(start_R)
            wirePower = self.generateWireCompensatedPower(config, wire_length, wirePower)

        # - Enable wire
        GCODE += self.generateWireEnable(config, wirePower)

        return GCODE

    def generateEndBlock(self, config):
        GCODE = "\n"
        GCODE += self.makeCommentedLine(config, "*** END BLOCK ***") + "\n"

        # - Disable wire
        GCODE += self.generateWireDisable(config)

        # - Up wire at current position to park height
        if config.EnableParking:
            GCODE += self.makeCommentedLine(config, "- Parking -") + "\n"
            up_posistion  = "%s%.2f %s%.2f" % (config.Z1AxisName, config.ParkZ, config.Z2AxisName, config.ParkZ)
            feed_rate     = config.FeedRateMove
            curX1 = self._current_L[0] if self._current_L is not None else 0.0
            curX2 = self._current_R[0] if self._current_R is not None else 0.0
            feed = self._calculateFeed(config, feed_rate, curX1, config.ParkZ, curX2, config.ParkZ)
            # - G94 keeps today's str() formatting (e.g. F1800.0); G93 uses %.2f
            feed_str = str(feed) if not self._g93_emitted else "%.2f" % feed
            self._addTravelTime(config, feed_rate, curX1, config.ParkZ, curX2, config.ParkZ, True)
            self._setCurrent(curX1, config.ParkZ, curX2, config.ParkZ)
            GCODE += config.MoveCommand.replace("{Position}", up_posistion).replace("{FeedRate}", feed_str) + "\n"

        # - Park XZ
        if config.EnableParking:
            GCODE += self.generateRapidTravel(config, config.ParkX, config.ParkZ, config.ParkX, config.ParkZ )
            # - Park R1
            if config.FiveAxisMachine:
                GCODE += self.generateRotation(config, config.MoveCommand, config.ParkR1, config.FeedRateRotate)
        
        if config.EndProgramCode:
            GCODE += "{}\n".format(config.EndProgramCode)
            
        return GCODE

    '''
    Make GCODE from rotation element
    @param rt - rotation object
    @param config - machine configuration
    @param angle (optional) - angle to emit; mirrored routes pass -Angle
    '''
    def makeGCODEFromRotation(self, rt, config, angle = None):
        if angle is None:
            angle = rt.Angle

        GCODE = "\n"
        GCODE += self.makeCommentedLine(config, "- Rotation [{}] -".format(rt.Label)) + "\n"

        # - Generate rotation command
        GCODE += self.generateRotation(config, config.MoveCommand, angle, config.FeedRateRotate)
        return GCODE

    '''
    Calculate dynamic power if needed and return gcode for command
    '''
    # pending removal
    def getDynamicWirePowerCommand(self, point1, point2, power, config):
        wirePowerCommand = ""
        # - generate compensated wire power
        if config.DynamicWirePower:
            # - Calculate wire length
            wire_length = point1.distanceToPoint(point2);
            wirePowerCommand = "S%.2f" % (self.generateWireCompensatedPower(config, wire_length, power))
        return wirePowerCommand
    
    '''
    Number of flattened route points consumed by one movement object.
    
    @param object - movement object from route.Objects
    @param first - True when this is the first movement of the route
    '''
    def _points_count_for_object(self, object, first):
        if object.Type == "Enter":
            return object.PointsCount + 1
        if object.Type == "Exit":
            return object.PointsCount
        return object.PointsCount if first else object.PointsCount - 1

    '''
    Expected total number of points in the source route's Offset_L / Offset_R
    '''
    def _expected_route_points(self, route):
        source = route.Proxy.getSourceRoute(route)
        count = 0
        for i in range(len(source.Data)):
            object = source.Objects[source.Data[i]]
            if object.Type == "Rotation":
                continue
            count += self._points_count_for_object(object, count == 0)
        return count

    '''
    Recompute routes saved with the previous (duplicate Exit point) layout.
    
    Route point layout changed together with the Postprocessor accounting. Older
    documents keep their stale Offset_L/Offset_R until the Route is touched, so
    refresh only when the stored length no longer matches the current builder.
    Route clones never store points; they resolve their source route.
    '''
    def _refresh_route_points(self, route):
        source = route.Proxy.getSourceRoute(route)
        expected = self._expected_route_points(route)
        if len(source.Offset_L) == expected and len(source.Offset_R) == expected:
            return

        doc = getattr(source, "Document", None)
        if doc is not None and hasattr(source, "touch"):
            source.touch()
            doc.recompute()

        expected = self._expected_route_points(route)
        if len(source.Offset_L) != expected or len(source.Offset_R) != expected:
            raise Exception(
                "ERROR: Route [{}] point data is out of date: {} points stored, {} expected. "
                "Recompute the route and try again.".format(
                    source.Label, len(source.Offset_L), expected))

    '''
    Generate GCODE from route
    '''
    def makeGCODE(self, route_list, config):
        TASK = "\n"
        # - Task GCODE buffer
        TASK += self.makeCommentedLine(config, "*** TASK BLOCK ***") + "\n"
        start_point = None

        # - Resolve clone sources and read the emitted points once per route
        route_points = []
        for route in route_list:
            self._refresh_route_points(route)
            points_L, points_R = route.Proxy.getOutputPoints(route)
            route_points.append((route, points_L, points_R))

        # find first point for start block
        for route, points_L, points_R in route_points:
            if len(points_L) > 0 and len(points_R) > 0:
                start_point = (points_L[0], points_R[0])
                break

        # ---- Generate startup block
        START = self.generateStartBlock(config, start_point)

        # - Switch to G93 right after the start block when it already established a
        #   known position (parking and/or homing enabled). Never emitted inside the
        #   start block.
        if config.FeedRateMode == utilities.FC_FEED_RATE_MODES[1] and not self._g93_emitted and self._current_L is not None:
            START += self.makeCommentedLine(config, "Set G93 inverse time feed rate mode") + "\n"
            START += "G93\n"
            self._g93_emitted = True

        # - Wal all routes
        for route, points_L, points_R in route_points:
            source = route.Proxy.getSourceRoute(route)

            TASK += "\n"
            TASK += self.makeCommentedLine(config, "--- Route begin [{}] ---".format(route.Label)) + "\n"

            point_index = 0

            if len(points_L) > 0 or len(points_R) > 0:                
                # - Generate rapid travel command
                TASK += self.generateRapidTravel(config, points_L[0].y, points_L[0].z, points_R[0].y, points_R[0].z)
                # - Switch to G93 right after the first route-begin rapid if the
                #   start block did not establish a position.
                if config.FeedRateMode == utilities.FC_FEED_RATE_MODES[1] and not self._g93_emitted:
                    TASK += self.makeCommentedLine(config, "Set G93 inverse time feed rate mode") + "\n"
                    TASK += "G93\n"
                    self._g93_emitted = True
            
            for i in range(len(source.Data)):
                # - Access item
                object_index = source.Data[i]
                object = source.Objects[object_index]

                if object.Type == "Rotation": # - Make GCODE from rotation
                    angle = route.Proxy.getRotationAngle(route, object.Angle)
                    TASK += self.makeGCODEFromRotation(object, config, angle)
                else:
                    feed_override = source.FeedOverrides[i]

                    
                    addPause = object.AddPause if hasattr(object, "AddPause") else False
                    duration = object.PauseDuration if hasattr(object, "PauseDuration") else 0
                    feed = object.FeedRate if hasattr(object, "FeedRate") and object.FeedRate > 0 else config.FeedRateCut
                    feed = feed * feed_override
                        
                    power = float(object.WirePower) if hasattr(object, "WirePower") and object.WirePower > 0 else float(config.WireMinPower)
                    isRapid = object.RapidMove if hasattr(object, "RapidMove") else False
                    TASK += "\n"
                    TASK += self.makeCommentedLine(config, "- {} [{}]".format(object.Type, object.Label)) + "\n"

                    # The resolved route points are a continuous polyline:
                    # - each object's start point is shared with the previous object;
                    # - Enter prepends a synthetic plunge-down point and leaves its
                    #   last path point for the next object, so it consumes P + 1;
                    # - Exit keeps all of its path points and appends its plunge-up,
                    #   so it consumes P;
                    # - the first movement object also consumes the route-begin
                    #   target point, later movement objects consume P - 1.
                    # Points and move types must advance together; do not derive
                    # this from LEAD flags alone.
                    points_count = self._points_count_for_object(object, point_index == 0)

                    # - Step over each point
                    safe_height = float(object.SafeHeight) if hasattr(object, "SafeHeight") else None
                    for p_idx in range(points_count):
                        point_l = points_L[point_index]
                        point_r = points_R[point_index]

                        at_safe_height = safe_height is not None \
                            and point_l.z >= safe_height - 1e-6 \
                            and point_r.z >= safe_height - 1e-6

                        allowRapid = True
                        forceRapid = False

                        if object.Type == "Enter":
                            # The first Enter point is the synthetic plunge-down
                            # start. It is either the route-begin target or the
                            # Exit->Enter travel, both performed at safe height.
                            allowRapid = p_idx == 0 and at_safe_height
                            forceRapid = allowRapid
                        elif object.Type == "Exit":
                            # Lead-out and plunge-up must not be rapid cuts; only
                            # the final point (already at safe height) may be rapid.
                            allowRapid = p_idx == points_count - 1 and at_safe_height

                        wirePowerCommand = self.getDynamicWirePowerCommand(point_l, point_r, power, config)

                        if (isRapid or forceRapid) and allowRapid:
                            # - Generate rapid travel command
                            TASK += self.generateRapidTravel(config, point_l.y, point_l.z, point_r.y, point_r.z)
                        else:
                            # - Generate CUT travel command
                            TASK += self.generateTravel(config, config.CutCommand, feed, wirePowerCommand, point_l.y, point_l.z, point_r.y, point_r.z)

                        # - Increase point index
                        point_index += 1
                    
                    if addPause and duration > 0:
                        self._addPauseTime(duration)
                        if config.TimeUnits == utilities.FC_TIME_UNITS[1]: #["Seconds", "Milliseconds"]
                            duration = duration * 1000
                        TASK += self.generatePause(config.PauseCommand, duration)
            
            TASK += self.makeCommentedLine(config, "--- Route end [{}] ---".format(route.Label)) + "\n"
            TASK += "\n"

        #generate end block        
        END   = self.generateEndBlock(config)

        # - Expected run time is only known once every block has been generated
        run_time = self.formatRunTime(self._run_time_seconds)
        program = START.replace("{ExpectedRunTime}", run_time) + ''.join(TASK) + END

        App.Console.PrintMessage("GCODE generated (expected run time: %s)\n" % run_time)

        dialog = QtGui.QFileDialog()
        lastDir = dialog.directory().absolutePath()
        # - Open save file dialog
        save_path, save_filter = dialog.getSaveFileName(None, "Save GCODE", os.path.join(lastDir, route_list[0].Label), "*.gcode") # PySide

        # - Check path
        if save_path == "":
            App.Console.PrintWarning("GCODE saving aborted (no output file path specified)\n")
        else:
            try:
                with open(save_path, "w") as f:
                    f.write(program)
                App.Console.PrintMessage("GCODE saved into [%s]\n" % save_path)
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
        if config is None:
            QtGui.QMessageBox.critical(None, "Config not found.", "Config [{}] not found in active document.".format(group.ConfigName))
            return

        # - Check routes type
        for route in routes:
            if not hasattr(route, "Type") or route.Type not in ROUTE_TYPES:
                QtGui.QMessageBox.critical(None, "Error generating Gcode", "Object type not supported. Check Selected objects.")
                return
        
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
                if not hasattr(route, "Type") or route.Type not in ROUTE_TYPES:
                    return False
                
            job_name = routes[0].JobName
            for  route in routes:
                if route.JobName != job_name:
                    return False
                
            return True
            
Gui.addCommand("MakeGcode", Postprocess())
