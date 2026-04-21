import FreeCAD
import Import
import json

doc_name = "InspectOrigin"
if doc_name in FreeCAD.listDocuments():
    FreeCAD.closeDocument(doc_name)
doc = FreeCAD.newDocument(doc_name)

# Re-import the assembly we previously created to examine how Parts are structured
Import.insert("/mnt/d/workspace/skills_test/examples/SampleModifiedAssembly.step", doc.Name)
doc.recompute()

# Examine a known good Part (e.g., P018_part or any with Origin)
info = []
for o in doc.Objects:
    if o.TypeId == "App::Part":
        rec = {
            "name": o.Name,
            "label": o.Label,
            "type": o.TypeId,
            "group": [c.Name for c in (o.Group or [])],
        }
        info.append(rec)
    if o.TypeId == "App::Origin":
        rec = {
            "name": o.Name,
            "label": o.Label,
            "type": o.TypeId,
            "origin_features": [(f.Name, f.Role if hasattr(f, "Role") else None, f.TypeId) for f in (o.OriginFeatures or [])],
        }
        info.append(rec)
    if o.TypeId in ("App::Line", "App::Plane"):
        info.append({
            "name": o.Name,
            "label": o.Label,
            "type": o.TypeId,
            "role": o.Role if hasattr(o, "Role") else None,
            "placement": [list(o.Placement.Base), [o.Placement.Rotation.Axis.x, o.Placement.Rotation.Axis.y, o.Placement.Rotation.Axis.z, o.Placement.Rotation.Angle]],
        })

print(json.dumps(info[:20], indent=2))

FreeCAD.closeDocument(doc_name)
