# -*- coding: utf-8 -*-
"""Job task panel tests. Run via FreeCADCmd.exe tests/test_job_panel.py

The panel model tests are pure Python. The widget tests create a Qt application
in offscreen mode and are skipped when Qt cannot create one in this process.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import FreeCAD
App = FreeCAD
import FreeCADGui
FreeCADGui.addCommand = lambda *a, **k: None

import InitMachine
import JobConfig
import MachineGui
import TaskPanelBase
import utilities

QT_AVAILABLE = False
try:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide import QtGui, QtWidgets
    _APPLICATION = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    QT_AVAILABLE = True
except Exception:
    QtGui = None
    _APPLICATION = None


def new_job_document(name = "JobPanel"):
    doc = App.newDocument(name)
    job = doc.addObject("App::DocumentObjectGroupPython", "Job")
    InitMachine.Machine(job, job.Name)
    doc.recompute()
    return doc, job


def propertySnapshot(obj):
    return {name: repr(getattr(obj, name)) for name in JobConfig.configPropertyNames(obj)}


class FakeGui:
    '''Minimal FreeCADGui replacement for task panel accept/reject.'''

    def __init__(self):
        self.ActiveDocument = None
        self.Control = type("Control", (), {"closeDialog": staticmethod(lambda: None)})()


class TestPropertyLabels(unittest.TestCase):
    def test_labels_are_human_readable(self):
        cases = {
            "FiveAxisMachine": "Five axis machine",
            "FieldWidth": "Field width",
            "X1AxisName": "X1 axis name",
            "R1AxisName": "R1 axis name",
            "BlockPosition": "Block position",
            "FeedRateMode": "Feed rate mode",
            "OriginX": "Origin X",
            "OriginRotationX": "Origin rotation X",
        }
        for name, label in cases.items():
            self.assertEqual(MachineGui.propertyLabel(name), label)


class TestPanelModel(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_job_document()

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def panelNames(self):
        return [name for _, names in MachineGui.panelProperties(self.job) for name in names]

    def test_one_page_per_property_group_in_panel_order(self):
        groups = [group for group, _ in MachineGui.panelProperties(self.job)]
        self.assertEqual(groups, [group for group in MachineGui.GROUP_ORDER if group in groups])
        self.assertEqual(len(groups), len(set(groups)))
        self.assertEqual(groups[0], "Machine Geometry")
        self.assertEqual(groups[-1], "GCODE")
        self.assertIn("Homing/Parking", groups)
        self.assertNotIn("Homing", groups)
        self.assertNotIn("Parking", groups)
        self.assertLess(groups.index("Homing/Parking"), groups.index("GCODE"))

    def test_preferred_rows_are_ordered(self):
        groups = dict(MachineGui.panelProperties(self.job))
        self.assertEqual(groups["Machine Geometry"],
                         ["FiveAxisMachine", "HorizontalTravel", "VerticalTravel",
                          "FieldWidth", "OriginX", "OriginRotationX"])
        self.assertEqual(groups["Foam Block"],
                         ["BlockWidth", "BlockLength", "BlockHeight", "BlockPosition"])
        self.assertEqual(groups["Homing/Parking"],
                         ["EnableHoming", "HomingX1", "HomingZ1", "HomingX2", "HomingZ2",
                          "HomingR1", "EnableParking", "ParkX", "ParkZ", "ParkR1"])

    def test_merged_group_keeps_property_editor_groups(self):
        # - Merging is a panel presentation detail; the property editor groups stay.
        self.assertEqual(self.job.getGroupOfProperty("EnableHoming"), "Homing")
        self.assertEqual(self.job.getGroupOfProperty("EnableParking"), "Parking")
        self.assertIn("Homing/Parking", dict(MachineGui.panelProperties(self.job)))

    def test_every_config_property_is_covered_exactly_once(self):
        names = self.panelNames()
        self.assertEqual(len(names), len(set(names)))

        config = JobConfig.configPropertyNames(self.job)
        for name in config:
            group = self.job.getGroupOfProperty(name) or MachineGui.DEFAULT_GROUP
            peers = [other for other in config
                     if (self.job.getGroupOfProperty(other) or MachineGui.DEFAULT_GROUP) == group]
            visible = any("Hidden" not in self.job.getEditorMode(other) for other in peers)
            if visible:
                self.assertIn(name, names)
            else:
                self.assertNotIn(name, names)

    def test_hidden_rows_stay_in_their_group(self):
        names = self.panelNames()
        # - Hidden until EnableHoming/EnableParking are checked; they must still
        #   have rows, in one merged group.
        self.assertIn("HomingX1", names)
        self.assertIn("ParkX", names)
        self.assertIn("HomingCommand", names)

    def test_reserved_and_internal_properties_are_not_part_of_the_panel(self):
        names = self.panelNames()
        for name in ("Label", "Proxy", "Group", "Type", "Visibility", "_GroupTouched"):
            self.assertNotIn(name, names)

    def test_all_panel_properties_have_supported_types(self):
        for name in self.panelNames():
            type_id = self.job.getTypeIdOfProperty(name)
            self.assertTrue(MachineGui.supportsPropertyType(type_id),
                            "{} uses unsupported {}".format(name, type_id))

    def test_unknown_property_type_is_not_claimed_as_supported(self):
        self.assertFalse(MachineGui.supportsPropertyType("App::PropertyLinkList"))


class TestPanelDefinition(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_job_document("JobPanelDefinition")

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def test_panel_is_a_task_panel(self):
        self.assertTrue(issubclass(MachineGui.JobTaskPanel, TaskPanelBase.BaseTaskPanel))
        self.assertTrue(hasattr(MachineGui.MachineVP, "doubleClicked"))

    def test_panel_snapshots_every_config_property(self):
        panel = MachineGui.JobTaskPanel.__new__(MachineGui.JobTaskPanel)
        panel.obj = self.job

        self.assertEqual(panel.properties(), JobConfig.configPropertyNames(self.job))

    def test_value_comparison(self):
        same = MachineGui.JobTaskPanel.sameValue
        self.assertTrue(same(1.0, 1.0))
        self.assertFalse(same(1.0, 1.0001))
        self.assertTrue(same(True, True))
        self.assertFalse(same(True, False))
        self.assertTrue(same("G93", "G93"))
        self.assertFalse(same("G93", "G94"))
        self.assertTrue(same(5, 5))
        self.assertTrue(same(App.Vector(1.0, 2.0, 3.0), App.Vector(1.0, 2.0, 3.0)))
        self.assertFalse(same(App.Vector(1.0, 2.0, 3.0), App.Vector(1.0, 2.0, 4.0)))
        # - Quantities compare by their base value.
        self.assertTrue(same(self.job.FieldWidth, float(self.job.FieldWidth)))

    def test_show_requires_a_migrated_job(self):
        self.assertFalse(MachineGui.showJobPanel(None))
        self.assertFalse(MachineGui.openJobPanel(None))

        other = self.doc.addObject("App::FeaturePython", "Other")
        self.assertFalse(MachineGui.showJobPanel(other))

        old = self.doc.addObject("App::DocumentObjectGroupPython", "OldJob")
        old.addProperty("App::PropertyString", "Type", "", "")
        old.Type = "Job"
        self.assertFalse(MachineGui.showJobPanel(old))
        self.assertFalse(MachineGui.openJobPanel(old))

    def test_active_dialog_blocks_a_second_panel(self):
        class BlockingControl:
            @staticmethod
            def activeDialog():
                return True

            @staticmethod
            def showDialog(panel):
                raise AssertionError("a second task dialog must not be built")

        original = MachineGui.Gui
        MachineGui.Gui = type("Gui", (), {"Control": BlockingControl})()
        try:
            self.assertFalse(MachineGui.showJobPanel(self.job))
        finally:
            MachineGui.Gui = original

    def test_show_clears_the_job_selection(self):
        calls = []

        class FakeControl:
            @staticmethod
            def activeDialog():
                return False

            @staticmethod
            def showDialog(panel):
                calls.append(("show", panel))

        class FakeSelection:
            @staticmethod
            def isSelected(obj):
                return True

            @staticmethod
            def removeSelection(obj):
                calls.append(("remove", obj))

        original_gui = MachineGui.Gui
        original_panel = MachineGui.JobTaskPanel
        MachineGui.Gui = type("Gui", (), {"Control": FakeControl, "Selection": FakeSelection})()
        MachineGui.JobTaskPanel = lambda obj, created = False: "panel"
        try:
            self.assertTrue(MachineGui.showJobPanel(self.job, created = True))
        finally:
            MachineGui.Gui = original_gui
            MachineGui.JobTaskPanel = original_panel

        # - The Job is deselected before the panel is shown, so the machine
        #   graphics never appear in the selection color while editing.
        self.assertEqual(calls, [("remove", self.job), ("show", "panel")])


@unittest.skipUnless(QT_AVAILABLE, "Qt application is not available in this process")
class TestPanelWidgets(unittest.TestCase):
    def setUp(self):
        self.doc, self.job = new_job_document("JobPanelWidgets")
        self.panel = None

    def tearDown(self):
        if self.doc.getBookedTransactionID() != 0:
            self.doc.abortTransaction()
        App.closeDocument(self.doc.Name)

    def openPanel(self):
        self.panel = MachineGui.JobTaskPanel(self.job)
        return self.panel

    def test_groups_follow_the_panel_model(self):
        panel = self.openPanel()
        expected = MachineGui.panelProperties(self.job)

        self.assertEqual([panel._selector.itemText(index) for index in range(panel._selector.count())],
                         [group for group, _ in expected])
        self.assertEqual(panel._pages.count(), len(expected))
        self.assertEqual(len(panel._rows), sum(len(names) for _, names in expected))

        for index, (group, names) in enumerate(expected):
            panel._selector.setCurrentIndex(index)
            self.assertEqual(panel._pages.currentIndex(), index)
            self.assertEqual(panel._pages.widget(index).layout().rowCount(), len(names))

    def test_opening_does_not_change_any_value(self):
        before = propertySnapshot(self.job)
        self.openPanel()
        self.assertEqual(propertySnapshot(self.job), before)

    def test_number_editor_uses_preferred_units(self):
        panel = self.openPanel()
        row = panel.row("FieldWidth")
        self.assertTrue(row.widget.suffix().strip())
        row.widget.setValue(float(row.widget.value()) + 10.0)
        self.assertAlmostEqual(float(self.job.FieldWidth), row.read(), places = 6)

    def test_vector_editor(self):
        panel = self.openPanel()
        row = panel.row("BlockPosition")
        self.assertEqual(len(row.widget.findChildren(QtGui.QDoubleSpinBox)), 3)
        first = row.widget.layout().itemAt(1).widget()
        first.setValue(float(first.value()) + 5.0)
        self.assertAlmostEqual(self.job.BlockPosition.x, row.read().x, places = 6)

    def test_enumeration_editor(self):
        panel = self.openPanel()
        panel.row("FeedRateMode").widget.setCurrentText("G94")
        self.assertEqual(self.job.FeedRateMode, "G94")

    def test_string_editor(self):
        panel = self.openPanel()
        panel.row("StartProgramCode").widget.setText("%")
        self.assertEqual(self.job.StartProgramCode, "%")

    def test_toggle_reveals_dependent_rows(self):
        panel = self.openPanel()
        self.assertFalse(panel.row("HomingX1").isVisible())
        self.assertFalse(panel.row("HomingCommand").isVisible())

        panel.row("EnableHoming").widget.setChecked(True)

        self.assertTrue(self.job.EnableHoming)
        self.assertTrue(panel.row("HomingX1").isVisible())
        self.assertTrue(panel.row("HomingCommand").isVisible())

        panel.row("HomingX1").widget.setValue(123.0)
        self.assertAlmostEqual(float(self.job.HomingX1), panel.row("HomingX1").read(), places = 6)

    def test_untouched_rows_are_not_written_back(self):
        panel = self.openPanel()
        self.job.FieldWidth = 999.0
        panel.row("SafeHeight").widget.setValue(float(panel.row("SafeHeight").widget.value()) + 5.0)
        self.assertAlmostEqual(float(self.job.FieldWidth), 999.0, places = 6)

    def test_expression_bound_property_is_read_only(self):
        other = self.doc.addObject("App::FeaturePython", "Other")
        other.addProperty("App::PropertyLength", "Width", "", "")
        other.Width = 500.0
        self.job.setExpression(".FieldWidth", "<<Other>>.Width")
        self.doc.recompute()

        panel = self.openPanel()
        row = panel.row("FieldWidth")
        self.assertFalse(row.widget.isEnabled())
        self.assertIn("expression", row.label.toolTip().lower())

        row.widget.setValue(1000.0)
        self.assertAlmostEqual(float(self.job.FieldWidth), 500.0, places = 6)

    def test_cancel_restores_original_values(self):
        self.openPanel()
        original = float(self.job.FieldWidth)
        self.panel.row("FieldWidth").widget.setValue(original + 100.0)
        self.assertNotAlmostEqual(float(self.job.FieldWidth), original, places = 3)

        self.panel.restoreOriginal()
        self.assertAlmostEqual(float(self.job.FieldWidth), original, places = 6)

    def test_accept_commits_the_edited_values(self):
        panel = self.openPanel()
        row = panel.row("FieldWidth")
        row.widget.setValue(float(row.widget.value()) + 20.0)
        expected = row.read()

        original_machine_gui = MachineGui.Gui
        original_task_gui = TaskPanelBase.Gui
        MachineGui.Gui = FakeGui()
        TaskPanelBase.Gui = FakeGui()
        try:
            self.assertTrue(panel.accept())
        finally:
            MachineGui.Gui = original_machine_gui
            TaskPanelBase.Gui = original_task_gui

        self.assertEqual(self.doc.getBookedTransactionID(), 0)
        self.assertAlmostEqual(float(self.job.FieldWidth), expected, places = 6)

    def test_cancelled_creation_removes_the_job(self):
        name = self.job.Name
        panel = MachineGui.JobTaskPanel(self.job, created = True)
        panel.row("FieldWidth").widget.setValue(float(panel.row("FieldWidth").widget.value()) + 10.0)

        original_machine_gui = MachineGui.Gui
        original_task_gui = TaskPanelBase.Gui
        MachineGui.Gui = FakeGui()
        TaskPanelBase.Gui = FakeGui()
        try:
            self.assertTrue(panel.reject())
        finally:
            MachineGui.Gui = original_machine_gui
            TaskPanelBase.Gui = original_task_gui

        self.assertIsNone(self.doc.getObject(name))
        self.assertEqual(self.doc.getBookedTransactionID(), 0)


class TestGuiIntegration(unittest.TestCase):
    '''Wiring checks with fake GUI pieces; no widgets are created here.'''

    def setUp(self):
        self.original_gui = MachineGui.Gui
        self.original_utilities_gui = utilities.Gui
        self.original_view_provider = MachineGui.MachineVP
        self.original_show = MachineGui.showJobPanel
        self.view = type("View", (), {
            "active": None,
            "setActiveObject": lambda self, kind, obj: setattr(self, "active", obj),
            "getActiveObject": lambda self, kind: self.active,
        })()
        self.fake_gui = type("Gui", (), {
            "ActiveDocument": type("Document", (), {"ActiveView": self.view})(),
        })()
        MachineGui.Gui = self.fake_gui
        utilities.Gui = self.fake_gui
        MachineGui.MachineVP = lambda view_object: None
        self.opened = []
        MachineGui.showJobPanel = lambda obj, created = False: self.opened.append((obj, created)) or True

    def tearDown(self):
        MachineGui.Gui = self.original_gui
        utilities.Gui = self.original_utilities_gui
        MachineGui.MachineVP = self.original_view_provider
        MachineGui.showJobPanel = self.original_show

    def test_init_machine_opens_the_job_panel(self):
        doc = App.newDocument("JobPanelCreation")
        try:
            MachineGui.InitMachine().Activated()

            job = doc.getObject("Job")
            self.assertIsNotNone(job)
            self.assertEqual(job.Type, "Job")
            self.assertEqual(len(self.opened), 1)
            self.assertIs(self.opened[0][0], job)
            self.assertTrue(self.opened[0][1])
            self.assertIs(self.view.getActiveObject(utilities.ACTIVE_JOB_KEY), job)
        finally:
            App.closeDocument(doc.Name)

    def test_init_machine_creates_several_setups(self):
        doc = App.newDocument("JobPanelMulti")
        try:
            self.assertTrue(MachineGui.InitMachine().IsActive())
            MachineGui.InitMachine().Activated()
            self.assertTrue(MachineGui.InitMachine().IsActive())
            MachineGui.InitMachine().Activated()

            jobs = [obj for obj in doc.Objects if getattr(obj, "Type", None) == "Job"]
            self.assertEqual(len(jobs), 2)
            self.assertIs(self.view.getActiveObject(utilities.ACTIVE_JOB_KEY), jobs[-1])
        finally:
            App.closeDocument(doc.Name)

    def test_failed_creation_removes_the_job(self):
        doc = App.newDocument("JobPanelCreationError")
        original_machine = InitMachine.Machine

        def broken_machine(obj, job_name):
            raise Exception("boom")

        InitMachine.Machine = broken_machine
        try:
            MachineGui.InitMachine().Activated()
            self.assertIsNone(doc.getObject("Job"))
            self.assertEqual(self.opened, [])
        finally:
            InitMachine.Machine = original_machine
            App.closeDocument(doc.Name)

    def test_double_click_opens_the_panel(self):
        doc, job = new_job_document("JobPanelDoubleClick")
        try:
            provider_class = self.original_view_provider
            provider = provider_class.__new__(provider_class)
            provider.Object = job
            view_object = type("ViewObject", (), {"Object": job})()

            self.assertTrue(provider.doubleClicked(view_object))
            self.assertEqual(self.opened, [(job, False)])
        finally:
            App.closeDocument(doc.Name)

    def test_double_click_on_unmigrated_job_uses_default_behaviour(self):
        doc = App.newDocument("JobPanelDoubleClickOld")
        try:
            old = doc.addObject("App::DocumentObjectGroupPython", "OldJob")
            old.addProperty("App::PropertyString", "Type", "", "")
            old.Type = "Job"

            provider_class = self.original_view_provider
            provider = provider_class.__new__(provider_class)
            provider.Object = old
            view_object = type("ViewObject", (), {"Object": old})()

            # - showJobPanel is patched to True, so test the real function path
            MachineGui.showJobPanel = self.original_show
            self.assertFalse(provider.doubleClicked(view_object))
            self.assertEqual(self.opened, [])
        finally:
            App.closeDocument(doc.Name)


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
