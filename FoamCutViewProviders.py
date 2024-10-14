import FreeCAD
from utilities import isNewStateHandling
import pivy.coin as coin

class FoamCutBaseViewProvider:
    def __init__(self, obj):
        self.Object = obj.Object
        obj.Proxy = self

    def attach(self, obj):
        self.ViewObject = obj
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
    
class FoamCutMovementViewProvider(FoamCutBaseViewProvider):
    def __init__(self, obj):
        super().__init__(obj)
        obj.addProperty("App::PropertyBool",        "ShowProjectionLines",  "Task", "Show projection lines between planes").ShowProjectionLines = False

    def attach(self, obj):
        super().attach(obj)
        self.projection = coin.SoGroup()
        obj.RootNode.addChild(self.projection)      

    def drawProjections(self):
        print("drawProjections from {}".format(self.ViewObject)) 

        if not hasattr(self.ViewObject, "ShowProjectionLines") or not hasattr(self.Object, "Path_L") or not hasattr(self.Object, "Path_R"):            
            return

        while self.projection.getNumChildren() > 0:
            self.projection.removeChild(0)

        if self.ViewObject.ShowProjectionLines:
            style=coin.SoDrawStyle()
            style.style = coin.SoDrawStyle.LINES

            color = coin.SoBaseColor()
            color.rgb.setValue(0, 0, 1)

            self.projection.addChild(style)
            self.projection.addChild(color)

            lines = [(self.Object.Path_L[0], self.Object.Path_R[0]), (self.Object.Path_L[-1], self.Object.Path_R[-1])]

            for i in range(len(lines)):
                sep = coin.SoSeparator()
                line = coin.SoLineSet()
                line.numVertices.setValue(len(lines[i]))
                points = []
                for p in lines[i]:
                    points.append((p.x, p.y, p.z))
                coords = coin.SoCoordinate3()
                coords.point.setValues(0, points)

                sep.addChild(coords)
                sep.addChild(line)
                self.projection.addChild(sep)

    def updateData(self, fp, prop):   
        if prop == "Path_R" or prop == "Path_L":
            self.drawProjections()
        
    def onChanged(self, vp, prop):
        if prop == "ShowProjectionLines":
            self.drawProjections()