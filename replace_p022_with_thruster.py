import json
from pathlib import Path

import FreeCAD as App
import Part

STEP_PATH = Path("/mnt/c/Users/dell/freecad_data/DawnAerospace_B1_Thruster.STEP")
DOC_NAME = "test1"
PART_NAME = "P022_part"
OBJ_NAME = "P022"
TARGET_MIN = App.Vector(-40.0, -291.35540092679645, -69.5)
EXPORT_STEP = Path("/mnt/d/workspace/skills_test/examples/test1.step")


def remove_object(doc, obj):
    for child in list(getattr(obj, "OutList", [])):
        remove_object(doc, child)
    doc.removeObject(obj.Name)


doc = App.getDocument(DOC_NAME)
if doc is None:
    raise RuntimeError(f"Document not found: {DOC_NAME}")

part = doc.getObject(PART_NAME)
if part is None:
    raise RuntimeError(f"Container not found: {PART_NAME}")

old_obj = doc.getObject(OBJ_NAME)
old_color = (0.3921568691730499, 1.0, 0.5882353186607361, 1.0)
old_transparency = 40
if old_obj is not None:
    if hasattr(old_obj, "ViewObject"):
        try:
            old_color = tuple(old_obj.ViewObject.ShapeColor)
        except Exception:
            pass
        try:
            old_transparency = int(old_obj.ViewObject.Transparency)
        except Exception:
            pass
    remove_object(doc, old_obj)
    doc.recompute()

shape = Part.Shape()
shape.read(str(STEP_PATH))
if shape.isNull():
    raise RuntimeError(f"Failed to read STEP shape: {STEP_PATH}")

bbox = shape.BoundBox
translation = App.Vector(
    TARGET_MIN.x - bbox.XMin,
    TARGET_MIN.y - bbox.YMin,
    TARGET_MIN.z - bbox.ZMin,
)
placement = App.Placement(translation, App.Rotation())

new_obj = doc.addObject("Part::Feature", OBJ_NAME)
new_obj.Shape = shape
new_obj.Placement = placement
part.addObject(new_obj)

if hasattr(new_obj, "ViewObject"):
    new_obj.ViewObject.ShapeColor = old_color
    new_obj.ViewObject.Transparency = old_transparency

doc.recompute()

try:
    import FreeCADGui as Gui

    Gui.ActiveDocument.ActiveView.viewIsometric()
    Gui.SendMsgToActiveView("ViewFit")
except Exception:
    pass

import Import

assembly = doc.getObject("Assembly")
if assembly is not None:
    Import.export([assembly], str(EXPORT_STEP))

new_bbox = new_obj.Shape.BoundBox
result = {
    "document": DOC_NAME,
    "object": OBJ_NAME,
    "part_container": PART_NAME,
    "source_step": str(STEP_PATH),
    "target_min": [TARGET_MIN.x, TARGET_MIN.y, TARGET_MIN.z],
    "new_bbox_min": [new_bbox.XMin, new_bbox.YMin, new_bbox.ZMin],
    "new_bbox_max": [new_bbox.XMax, new_bbox.YMax, new_bbox.ZMax],
    "export_step": str(EXPORT_STEP),
}
print(json.dumps(result, ensure_ascii=True))
