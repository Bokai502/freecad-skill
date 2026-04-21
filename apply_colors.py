import FreeCAD

DOC_NAME = "SampleModifiedAssembly"

# name -> (r, g, b) float 0..1
COLORS = {
    "P018": (1.0, 0.7843, 0.3922),
    "P006": (1.0, 0.7843, 0.3922),
    "P020": (0.3922, 1.0, 0.5882),
    "P001": (0.3922, 0.5882, 1.0),
    "P015": (0.3922, 0.5882, 1.0),
    "P003": (1.0, 0.7843, 0.3922),
    "P004": (0.3922, 0.5882, 1.0),
    "P011": (0.3922, 0.5882, 1.0),
    "P017": (0.3922, 0.5882, 1.0),
    "P014": (0.3922, 1.0, 0.5882),
    "P008": (0.3922, 0.5882, 1.0),
    "P013": (1.0, 0.7843, 0.3922),
    "P019": (1.0, 0.7843, 0.3922),
    "P005": (0.3922, 0.5882, 1.0),
    "P016": (1.0, 0.7843, 0.3922),
    "P000": (0.3922, 1.0, 0.5882),
    "P010": (0.3922, 1.0, 0.5882),
    "P012": (0.3922, 1.0, 0.5882),
    "P002": (0.3922, 0.5882, 1.0),
    "P009": (0.3922, 1.0, 0.5882),
    "P007": (0.3922, 0.5882, 1.0),
    "P021": (1.0, 0.7843, 0.3922),
    "P022": (0.3922, 1.0, 0.5882),
}

doc = FreeCAD.getDocument(DOC_NAME)

def find_part(name):
    for obj in doc.Objects:
        if obj.Name == f"{name}_part" or obj.Label == f"{name}_part":
            return obj
    return None

def iter_solids(container):
    out = []
    stack = list(container.Group) if hasattr(container, "Group") else []
    while stack:
        o = stack.pop()
        if hasattr(o, "Group") and o.Group:
            stack.extend(o.Group)
        if hasattr(o, "Shape") and o.Shape is not None and o.Shape.Solids:
            out.append(o)
    return out

applied = []
missing = []
for name, (r, g, b) in COLORS.items():
    part = find_part(name)
    if not part:
        missing.append(name)
        continue
    solids = iter_solids(part)
    if not solids:
        missing.append(f"{name}(no-solids)")
        continue
    for solid in solids:
        if solid.ViewObject is not None:
            solid.ViewObject.ShapeColor = (r, g, b)
            solid.ViewObject.Transparency = 40
    applied.append(name)

for obj in doc.Objects:
    if obj.Name == "EnvelopeShell" or obj.Label == "EnvelopeShell":
        if obj.ViewObject is not None:
            obj.ViewObject.DisplayMode = "Wireframe"
            obj.ViewObject.LineColor = (0.2, 0.5, 0.9)
            obj.ViewObject.LineWidth = 2.0

doc.recompute()
doc.save()

print(f"Applied: {len(applied)}/{len(COLORS)}")
if missing:
    print(f"Missing: {missing}")
