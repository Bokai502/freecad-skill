import FreeCAD
import json

doc_name = "VerifyP022"
if doc_name in FreeCAD.listDocuments():
    FreeCAD.closeDocument(doc_name)
doc = FreeCAD.open("/mnt/d/workspace/skills_test/examples/SampleModifiedAssembly.FCStd")

p022 = None
for o in doc.Objects:
    if o.Label == "P022_part" and o.TypeId == "App::Part":
        p022 = o
        break

result = {"found": p022 is not None}
if p022:
    result["name"] = p022.Name
    result["group"] = [(c.Name, c.TypeId) for c in (p022.Group or [])]
    for c in (p022.Group or []):
        if c.TypeId == "App::Origin":
            result["origin_features"] = [(f.Name, f.Role, f.TypeId) for f in (c.OriginFeatures or [])]
print(json.dumps(result, indent=2))

FreeCAD.closeDocument(doc.Name)
