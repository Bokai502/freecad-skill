import FreeCAD
import Import
import Part
import json

doc_name = "InspectThruster"
if doc_name in FreeCAD.listDocuments():
    FreeCAD.closeDocument(doc_name)
doc = FreeCAD.newDocument(doc_name)

Import.insert("/mnt/d/workspace/skills_test/DawnAerospace_B1_Thruster.STEP", doc.Name)
doc.recompute()

objs = [o for o in doc.Objects if hasattr(o, "Shape") and o.Shape is not None and not o.Shape.isNull()]
o = objs[0]
sh = o.Shape.copy()
sh.Placement = o.getGlobalPlacement()

bb = sh.BoundBox

# Instead of section, measure bounding box of shape intersected with a slab
def slab_extents(shape, axis, n=16):
    bb = shape.BoundBox
    if axis == 0:
        lo, hi = bb.XMin, bb.XMax
    elif axis == 1:
        lo, hi = bb.YMin, bb.YMax
    else:
        lo, hi = bb.ZMin, bb.ZMax
    results = []
    step = (hi - lo) / n
    for i in range(n):
        t0 = lo + step * i
        t1 = t0 + step
        # Build slab box
        if axis == 0:
            slab = Part.makeBox(step, 500, 500, FreeCAD.Vector(t0, -250, -250))
        elif axis == 1:
            slab = Part.makeBox(500, step, 500, FreeCAD.Vector(-250, t0, -250))
        else:
            slab = Part.makeBox(500, 500, step, FreeCAD.Vector(-250, -250, t0))
        try:
            common = shape.common(slab)
            if common.isNull():
                results.append((round((t0+t1)/2, 2), 0.0))
                continue
            cbb = common.BoundBox
            # cross-section extent (max of the two perpendicular axes)
            if axis == 0:
                xlen = cbb.YLength
                ylen = cbb.ZLength
            elif axis == 1:
                xlen = cbb.XLength
                ylen = cbb.ZLength
            else:
                xlen = cbb.XLength
                ylen = cbb.YLength
            vol = common.Volume if hasattr(common, "Volume") else 0.0
            results.append((round((t0+t1)/2, 2), round(xlen, 2), round(ylen, 2), round(vol, 2)))
        except Exception as e:
            results.append((round((t0+t1)/2, 2), str(e)))
    return results

result = {
    "bbox": {
        "x": [bb.XMin, bb.XMax, bb.XLength],
        "y": [bb.YMin, bb.YMax, bb.YLength],
        "z": [bb.ZMin, bb.ZMax, bb.ZLength],
    },
    "volume": sh.Volume,
    "y_slabs": slab_extents(sh, 1, n=12),
}
print(json.dumps(result, indent=2))

FreeCAD.closeDocument(doc_name)
