import FreeCAD
from utilities import isNewStateHandling

class FoamCutBaseViewProvider:
    def __init__(self, obj):
        obj.Proxy = self

    def attach(self, obj):
        self.Object = obj.Object

    def doubleClicked(self, obj):
        return True

    if isNewStateHandling(): # - currently supported only in main branch FreeCad v0.21.2 and up
        def dumps(self):
            return {"name": self.Object.Name}

        def loads(self, state):
            self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
            return None
    else:
        def __getstate__(self):
            return {"name": self.Object.Name}

        def __setstate__(self, state):
            self.Object = FreeCAD.ActiveDocument.getObject(state["name"])
            return None
    