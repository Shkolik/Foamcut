# -*- coding: utf-8 -*-

__title__ = "Foamcut migration"
__author__ = "Andrew Shkolik"
__license__ = "LGPL 2.1"
__doc__ = "One-time migration of old Foamcut documents to Job-owned configuration."

import re
import FreeCAD
App = FreeCAD
import JobConfig

CURRENT_VERSION = 4
_HELPER_NAMES = ("Origin", "CNCVolume", "WPL", "WPR", "Block", "RotationAxis")


def _config_reference_pattern(config):
    return re.compile(r"<<{}>>\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)".format(re.escape(config.Name)))


def _copy_config_properties(job, config):
    for name in config.PropertiesList:
        if name in JobConfig.RESERVED_PROPERTIES:
            continue
        if not hasattr(job, name):
            job.addProperty(
                config.getTypeIdOfProperty(name),
                name,
                config.getGroupOfProperty(name),
                config.getDocumentationOfProperty(name))
        setattr(job, name, getattr(config, name))


def _bind_job_links(doc, job):
    '''
    Give every child a hidden _Job link and point it at the real Job object.
    '''
    for obj in doc.Objects:
        if obj is job or getattr(obj, "JobName", None) != job.Name:
            continue
        if getattr(obj, "Type", None) in ("Helper", "RotationAxis"):
            continue
        if not hasattr(obj, "_Job"):
            obj.addProperty("App::PropertyLinkHidden", "_Job", "", "", 5)
        obj._Job = job


def _rewrite_expressions(doc, config, job):
    pattern = _config_reference_pattern(config)
    for obj in doc.Objects:
        if getattr(obj, "JobName", None) != job.Name:
            continue
        if getattr(obj, "Type", None) in ("Helper", "RotationAxis"):
            continue
        for path, expression in list(getattr(obj, "ExpressionEngine", [])):
            if config.Name not in expression:
                continue
            new_expression = pattern.sub(lambda match: "._Job.{}".format(match.group(1)), expression)
            if "<<{}>>".format(config.Name) in new_expression:
                raise Exception(
                    "Migration could not rewrite expression on {}: {}".format(obj.Label, expression))
            obj.setExpression(path, new_expression)


def _fix_job_references(doc, job):
    '''
    Normalize hidden Job references left by earlier/partial migrations.
    Some old files contain hiddenref(Job.Prop) or hiddenref(<<Job>>.Prop)
    while the actual Job object is named Job001 (FreeCAD renamed it because
    another object already used "Job"). Those expressions must point at the
    real Job name, otherwise every child reports "Property 'Job' not found".
    '''
    hidden = re.compile(
        r"hiddenref\(\s*(?:<<)?([A-Za-z_][A-Za-z0-9_]*)(?:>>)?\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\)")
    plain = re.compile(r"<<([A-Za-z_][A-Za-z0-9_]*)>>\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")
    config_ref = re.compile(r"<<Config>>\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)")

    def fix(expression):
        def hidden_repl(match):
            if match.group(1) in ("Job", job.Name):
                return "._Job.{}".format(match.group(2))
            return match.group(0)

        def plain_repl(match):
            if match.group(1) in ("Job", job.Name):
                return "._Job.{}".format(match.group(2))
            return match.group(0)

        expression = config_ref.sub(lambda match: "._Job.{}".format(match.group(1)), expression)
        return plain.sub(plain_repl, hidden.sub(hidden_repl, expression))

    for obj in doc.Objects:
        if getattr(obj, "JobName", None) != job.Name:
            continue
        if getattr(obj, "Type", None) in ("Helper", "RotationAxis"):
            continue
        for path, expression in list(getattr(obj, "ExpressionEngine", [])):
            new_expression = fix(expression)
            if new_expression != expression:
                obj.setExpression(path, new_expression)


def _capture_working_planes(job, doc):
    wpl_name = getattr(job, "WPLName", "")
    wpr_name = getattr(job, "WPRName", "")
    wpl = doc.getObject(wpl_name) if wpl_name else None
    wpr = doc.getObject(wpr_name) if wpr_name else None
    if wpl is None and wpr is None:
        return

    derived = {
        "left_x": -float(job.FieldWidth) / 2.0,
        "right_x": float(job.FieldWidth) / 2.0,
        "y": -float(job.OriginX),
        "length": float(job.HorizontalTravel),
        "width": float(job.VerticalTravel),
    }
    actual = dict(derived)
    if wpl is not None:
        actual["left_x"] = float(wpl.Position.x)
        actual["y"] = float(wpl.Position.y)
        actual["length"] = float(wpl.Length)
        actual["width"] = float(wpl.Width)
    if wpr is not None:
        actual["right_x"] = float(wpr.Position.x)
        actual["y"] = float(wpr.Position.y)
        actual["length"] = float(wpr.Length)
        actual["width"] = float(wpr.Width)

    if any(abs(actual[key] - derived[key]) > 1e-7 for key in derived):
        job.WorkingPlaneCustom = True
        job.WorkingPlaneLeftX = actual["left_x"]
        job.WorkingPlaneRightX = actual["right_x"]
        job.WorkingPlaneY = actual["y"]
        job.WorkingPlaneLength = actual["length"]
        job.WorkingPlaneWidth = actual["width"]


def _delete_helpers(job, doc, config):
    config_name = config.Name if config is not None else ""
    children = list(job.Group)
    for obj in children:
        obj_type = getattr(obj, "Type", None)
        if obj is config or obj_type in ("Helper", "RotationAxis") or obj.Name in _HELPER_NAMES:
            doc.removeObject(obj.Name)

    if config_name and doc.getObject(config_name) is not None:
        doc.removeObject(config_name)

    if hasattr(job, "ConfigName"):
        job.ConfigName = ""
    if hasattr(job, "WPLName"):
        job.WPLName = ""
    if hasattr(job, "WPRName"):
        job.WPRName = ""


def _migrate_job(job):
    doc = job.Document
    if not hasattr(job, "MigrationVersion"):
        job.addProperty("App::PropertyInteger", "MigrationVersion", "", "", 5)
        job.MigrationVersion = 0

    if job.MigrationVersion >= CURRENT_VERSION:
        return False

    config_name = getattr(job, "ConfigName", "")
    config = doc.getObject(config_name) if config_name else None

    JobConfig.applyConfigProperties(job)
    _bind_job_links(doc, job)

    if config is not None:
        _copy_config_properties(job, config)
        _capture_working_planes(job, doc)
        _rewrite_expressions(doc, config, job)

    _fix_job_references(doc, job)
    _delete_helpers(job, doc, config)

    job.MigrationVersion = CURRENT_VERSION
    for child in job.Group:
        if hasattr(child, "touch"):
            child.touch()
    return True


def migrate_document(doc=None, recompute=True):
    '''
    Migrate old Foamcut documents in one transaction.
    The Config object and the cosmetic helper objects are converted/removed together.
    @param doc (optional) - document to migrate; the active document by default
    @param recompute (optional) - recompute after commit. Pass False when called
                                  from onDocumentRestored, before the document's
                                  own recompute pass.
    @returns number of migrated jobs
    '''
    if doc is None:
        doc = App.ActiveDocument
    if doc is None:
        return 0

    jobs = [obj for obj in doc.Objects if getattr(obj, "Type", None) == "Job"]
    if not jobs:
        return 0

    jobs = [job for job in jobs if getattr(job, "MigrationVersion", 0) < CURRENT_VERSION]
    if not jobs:
        return 0

    doc.openTransaction("Migrate Foamcut job")
    migrated = 0
    try:
        for job in jobs:
            if _migrate_job(job):
                migrated += 1
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        App.Console.PrintError("Foamcut migration failed; document left unchanged\n")
        raise

    if migrated and recompute:
        doc.recompute()
        for job in jobs:
            try:
                view_object = getattr(job, "ViewObject", None)
                if view_object is not None and hasattr(view_object.Proxy, "draw"):
                    view_object.Proxy.draw()
            except Exception:
                pass
    return migrated


def _needs_migration(doc):
    jobs = [job for job in doc.Objects if getattr(job, "Type", None) == "Job"]
    if not jobs:
        return False
    if any(getattr(job, "MigrationVersion", 0) < CURRENT_VERSION for job in jobs):
        return True
    if any(getattr(job, "ConfigName", "") for job in jobs):
        return True
    # - Repair files that were partially migrated by an older build and now
    #   contain expressions pointing at a Config object that no longer exists.
    for obj in doc.Objects:
        if getattr(obj, "Type", None) in ("Helper", "RotationAxis"):
            continue
        for _, expression in getattr(obj, "ExpressionEngine", []):
            if "<<Config>>" in expression:
                return True
    return False


def needs_migration(doc):
    return _needs_migration(doc)


_prompted_documents = set()
_restoring_documents = set()


def prompt_migration(doc):
    '''
    Ask the user before converting an old document. The document has already
    been completely restored at this point, so Config and all helper objects
    are available and expressions can be rewritten safely.
    '''
    if doc is None or doc.Name in _prompted_documents:
        return
    if not _needs_migration(doc):
        return
    _prompted_documents.add(doc.Name)

    try:
        from PySide import QtGui
    except Exception:
        return

    answer = QtGui.QMessageBox.question(
        None,
        "Foamcut migration",
        "This document was created with an older Foamcut version.\n\n"
        "Migrate it now? The document will be converted to Job-owned "
        "configuration and the old Config/helper objects will be removed.\n\n"
        "It is recommended to keep a backup copy.",
        QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
        QtGui.QMessageBox.No)

    if answer != QtGui.QMessageBox.Yes:
        return

    try:
        migrate_document(doc, recompute = False)
        QtGui.QMessageBox.information(
            None,
            "Foamcut migration",
            "Migration complete. Recompute the document when you are ready "
            "to update the route geometry.")
    except Exception as error:
        QtGui.QMessageBox.critical(
            None,
            "Foamcut migration failed",
            "The document was left unchanged.\n\n{}".format(error))


class _DocumentObserver:
    def slotStartRestoreDocument(self, doc):
        _restoring_documents.add(doc.Name)

    def slotFinishRestoreDocument(self, doc):
        _restoring_documents.discard(doc.Name)
        prompt_migration(doc)

    def slotActivateDocument(self, doc):
        if doc.Name not in _restoring_documents:
            prompt_migration(doc)

    def slotCloseDocument(self, doc):
        _prompted_documents.discard(doc.Name)
        _restoring_documents.discard(doc.Name)


_observer = None


def install():
    global _observer
    if _observer is None:
        _observer = _DocumentObserver()
        App.addDocumentObserver(_observer)
    return _observer
