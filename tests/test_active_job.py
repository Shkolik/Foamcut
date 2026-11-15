# -*- coding: utf-8 -*-
"""Active Job (setup) resolution, activation and command gating tests.

Run via FreeCADCmd.exe tests/test_active_job.py
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
import MachineGui
import PathGui
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


class FakeView:
    def __init__(self):
        self.active = None
        self.keys = []

    def getActiveObject(self, key):
        return self.active

    def setActiveObject(self, key, obj):
        self.keys.append(key)
        self.active = obj


class FakeGui:
    def __init__(self):
        self.view = FakeView()
        self.ActiveDocument = type("Document", (), {"ActiveView": self.view})()


def new_document(name):
    doc = App.newDocument(name)
    job = InitMachine.createMachine(doc, recompute = False)
    doc.recompute()
    return doc, job


class TestActiveJobResolution(unittest.TestCase):
    def setUp(self):
        self.original_gui = utilities.Gui
        self.gui = FakeGui()
        utilities.Gui = self.gui
        self.documents = []

    def tearDown(self):
        utilities.Gui = self.original_gui
        for doc in self.documents:
            App.closeDocument(doc.Name)

    def add_document(self, name):
        doc, job = new_document(name)
        self.documents.append(doc)
        return doc, job

    def test_no_document_has_no_active_job(self):
        for doc in list(App.listDocuments().values()):
            App.closeDocument(doc.Name)
        self.assertIsNone(App.ActiveDocument)
        self.assertIsNone(utilities.getActiveJob())

    def test_no_job_in_document(self):
        doc = App.newDocument("NoJob")
        self.documents.append(doc)
        self.assertIsNone(utilities.getActiveJob(doc))
        self.assertIsNone(utilities.requireActiveJob("Cannot create", doc))

    def test_single_job_is_the_fallback(self):
        doc, job = self.add_document("SingleJob")
        self.gui.view.active = None
        self.assertIs(utilities.getActiveJob(doc), job)

    def test_several_jobs_need_an_active_one(self):
        doc, first = self.add_document("TwoJobs")
        second = InitMachine.createMachine(doc, recompute = False)
        doc.recompute()

        self.assertIsNone(utilities.getActiveJob(doc))
        self.assertIsNone(utilities.requireActiveJob("Cannot create", doc))

        utilities.setActiveJob(second)
        self.assertIs(utilities.getActiveJob(doc), second)

        utilities.setActiveJob(first)
        self.assertIs(utilities.getActiveJob(doc), first)

    def test_active_object_that_is_not_a_job_is_ignored(self):
        doc, job = self.add_document("BoxJob")
        box = doc.addObject("Part::Box", "Box")
        self.gui.view.active = box
        self.assertIs(utilities.getActiveJob(doc), job)

    def test_active_job_of_another_document_is_ignored(self):
        other_doc, other_job = self.add_document("OtherDoc")
        doc, first = self.add_document("CurrentDoc")
        second = InitMachine.createMachine(doc, recompute = False)
        doc.recompute()

        utilities.setActiveJob(other_job)
        self.assertIsNone(utilities.getActiveJob(doc))
        utilities.setActiveJob(second)
        self.assertIs(utilities.getActiveJob(doc), second)

    def test_set_active_job_uses_the_dedicated_key(self):
        doc, job = self.add_document("ActiveKey")
        utilities.setActiveJob(job)
        self.assertEqual(self.gui.view.keys, [utilities.ACTIVE_JOB_KEY])
        self.assertIs(self.gui.view.active, job)

    def test_headless_fallback_does_not_need_a_view(self):
        doc, job = self.add_document("Headless")
        utilities.Gui = self.original_gui
        self.assertIs(utilities.getActiveJob(doc), job)


class TestJobActivationUi(unittest.TestCase):
    def setUp(self):
        self.original_gui = utilities.Gui
        self.gui = FakeGui()
        utilities.Gui = self.gui
        self.original_show = MachineGui.showJobPanel
        self.opened = []
        MachineGui.showJobPanel = lambda obj, created = False: self.opened.append(obj) or True
        self.doc, self.job = new_document("JobActivation")
        self.view_object = type("ViewObject", (), {"Object": self.job})()

    def tearDown(self):
        MachineGui.showJobPanel = self.original_show
        utilities.Gui = self.original_gui
        App.closeDocument(self.doc.Name)

    def make_provider(self):
        provider = MachineGui.MachineVP.__new__(MachineGui.MachineVP)
        provider.Object = self.job
        return provider

    def test_double_click_activates_and_opens_the_panel(self):
        provider = self.make_provider()
        self.assertTrue(provider.doubleClicked(self.view_object))
        self.assertIs(self.gui.view.active, self.job)
        self.assertEqual(self.opened, [self.job])

    @unittest.skipUnless(QT_AVAILABLE, "Qt could not be initialized")
    def test_context_menu_activates_and_edits(self):
        provider = self.make_provider()
        menu = QtGui.QMenu()
        provider.setupContextMenu(self.view_object, menu)

        self.assertEqual([action.text() for action in menu.actions()], ["Activate", "Edit setup"])

        menu.actions()[1].trigger()
        self.assertEqual(self.opened, [self.job])

        menu.actions()[0].trigger()
        self.assertIs(self.gui.view.active, self.job)

    def test_init_machine_stays_available_with_an_existing_job(self):
        self.assertTrue(MachineGui.InitMachine().IsActive())


class TestCommandGating(unittest.TestCase):
    '''Operation commands need an unambiguous target Job.'''

    def setUp(self):
        self.original_gui = utilities.Gui
        self.gui = FakeGui()
        utilities.Gui = self.gui

        self.original_selected = PathGui.getAllSelectedObjects
        self.original_planes = PathGui.getWorkingPlanes
        PathGui.getAllSelectedObjects = lambda include_faces = False: [
            (self.box, ("Edge1",)), (self.box, ("Edge2",))]
        PathGui.getWorkingPlanes = lambda job, doc: [object(), object()]

        self.doc = App.newDocument("CommandGating")
        self.box = self.doc.addObject("Part::Box", "Box")
        self.first = InitMachine.createMachine(self.doc, recompute = False)
        self.second = InitMachine.createMachine(self.doc, recompute = False)
        self.doc.recompute()

    def tearDown(self):
        PathGui.getAllSelectedObjects = self.original_selected
        PathGui.getWorkingPlanes = self.original_planes
        utilities.Gui = self.original_gui
        App.closeDocument(self.doc.Name)

    def test_command_needs_an_active_job_with_several_setups(self):
        self.assertFalse(PathGui.MakePath().IsActive())

        utilities.setActiveJob(self.second)
        self.assertTrue(PathGui.MakePath().IsActive())

    def test_single_job_is_used_without_activation(self):
        self.gui.view.active = None
        self.doc.removeObject(self.second.Name)
        self.assertTrue(PathGui.MakePath().IsActive())


if __name__ == "__main__" or (len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__)):
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        sys.exit(1)
