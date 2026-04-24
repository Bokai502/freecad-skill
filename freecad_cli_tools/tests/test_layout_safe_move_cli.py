from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from freecad_cli_tools.cli import layout_safe_move
from freecad_cli_tools.layout_dataset import (
    load_layout_dataset_files,
    normalize_layout_dataset,
)


def write_dataset(
    layout_path: Path,
    geom_path: Path,
    *,
    component_id: str = "P001",
    source_component_id: str = "P_001_internal",
    component_mount_face_id: str = "P001.local_xmax",
    mount_face_id: str = "cabin_auto_1.xmax",
    cabin_id: str | None = "cabin_auto_1",
    dims: list[float] | None = None,
    position: list[float] | None = None,
    clearance_mm: float = 0.0,
) -> None:
    dims = dims or [10.0, 10.0, 10.0]
    position = position or [40.0, 0.0, 0.0]
    known_install_faces = {
        "cabin_auto_1.xmax": {
            "id": "cabin_auto_1.xmax",
            "owner_id": "cabin_auto_1",
            "side": "inner",
            "plane_axis": 0,
            "plane_value": 50.0,
            "normal_sign": 1,
        },
        "outer.xmax_inner": {
            "id": "outer.xmax_inner",
            "owner_id": "outer_shell",
            "side": "inner",
            "plane_axis": 0,
            "plane_value": 50.0,
            "normal_sign": -1,
        },
        "outer.zmin_outer": {
            "id": "outer.zmin_outer",
            "owner_id": "outer_shell",
            "side": "outer",
            "plane_axis": 2,
            "plane_value": -55.0,
            "normal_sign": -1,
        },
        "outer.zmax_outer": {
            "id": "outer.zmax_outer",
            "owner_id": "outer_shell",
            "side": "outer",
            "plane_axis": 2,
            "plane_value": 55.0,
            "normal_sign": 1,
        },
    }
    install_face_ids = {mount_face_id, "cabin_auto_1.xmax", "outer.zmin_outer", "outer.zmax_outer"}
    layout_topology = {
        "schema_version": "1.0",
        "layout_id": "layout-test",
        "source_design_id": "design-test",
        "outer_shell": {"id": "outer_shell", "source_ref": "outer_shell"},
        "cabins": [
            {
                "id": "cabin_auto_1",
                "parent": "outer_shell",
                "role": "internal_compartment",
            }
        ],
        "walls": [],
        "install_faces": [known_install_faces[face_id] for face_id in sorted(install_face_ids)],
        "placements": [
            {
                "component_id": component_id,
                "semantic_name": component_id,
                "kind": "internal" if cabin_id else "external",
                "cabin_id": cabin_id,
                "component_mount_face_id": component_mount_face_id,
                "mount_face_id": mount_face_id,
                "alignment": {
                    "normal_alignment": "opposite",
                    "component_u_axis_to_target_u_axis": True,
                    "in_plane_rotation_deg": 0.0,
                },
                "geometry_id": "G001",
                "thermal_id": "T001",
                "source_ref": {
                    "layout3dcube_component_id": source_component_id,
                },
            }
        ],
    }
    geom = {
        "schema_version": "2.0",
        "units": {"length": "mm", "mass": "kg", "power": "W"},
        "outer_shell": {
            "id": "outer_shell",
            "outer_bbox": {
                "min": [-55.0, -55.0, -55.0],
                "max": [55.0, 55.0, 55.0],
            },
            "inner_bbox": {
                "min": [-50.0, -50.0, -50.0],
                "max": [50.0, 50.0, 50.0],
            },
            "thickness": 5.0,
        },
        "install_faces": {
            face_id: {
                "id": known_install_faces[face_id]["id"],
                "belongs_to": (
                    "outer_shell"
                    if face_id.startswith("outer.")
                    else "cabin_auto_1"
                ),
                "side": known_install_faces[face_id]["side"],
                "cabin_face_tag": face_id.split(".", 1)[1].replace("_inner", "").replace("_outer", ""),
                "plane_axis": known_install_faces[face_id]["plane_axis"],
                "plane_value": known_install_faces[face_id]["plane_value"],
                "normal_sign": known_install_faces[face_id]["normal_sign"],
                "bbox_2d": [-50.0, 50.0, -50.0, 50.0],
                "center_xyz": [0.0, 0.0, 0.0],
                "extents_xyz": [0.0, 100.0, 100.0],
            }
            for face_id in sorted(install_face_ids)
        },
        "components": {
            source_component_id: {
                "id": source_component_id,
                "kind": "internal" if cabin_id else "external",
                "category": "avionics",
                "dims": dims,
                "mass": 1.0,
                "power": 2.0,
                "color": [255, 200, 100, 255],
                "clearance_mm": clearance_mm,
                "shape": "box",
                "model": "",
                "mount_face_id": mount_face_id,
                "position": position,
                "install_pos": position,
                "mount_point": [50.0, 5.0, 5.0],
                "leaf_node_id": "leaf.cabin_auto_1" if cabin_id else "leaf.outer",
                "thermal_surface": {},
                "thermal_interface": {},
                "thermoelastic": {},
            }
        },
    }
    layout_path.write_text(json.dumps(layout_topology, indent=2), encoding="utf-8")
    geom_path.write_text(json.dumps(geom, indent=2), encoding="utf-8")


def write_external_dataset(layout_path: Path, geom_path: Path) -> None:
    write_dataset(
        layout_path,
        geom_path,
        component_id="P022",
        source_component_id="P_022_external",
        component_mount_face_id="P022.local_zmin",
        mount_face_id="outer.zmax_outer",
        cabin_id=None,
        dims=[10.0, 20.0, 30.0],
        position=[1.0, 2.0, 55.0],
    )


def test_layout_safe_move_writes_registry_record(monkeypatch, tmp_path: Path) -> None:
    layout_path = tmp_path / "layout_topology.json"
    geom_path = tmp_path / "geom.json"
    output_layout_path = tmp_path / "layout_topology.updated.json"
    output_geom_path = tmp_path / "geom.updated.json"
    registry_dir = tmp_path / "registry"
    write_dataset(layout_path, geom_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-layout-safe-move",
            "--layout-topology",
            str(layout_path),
            "--geom",
            str(geom_path),
            "--layout-topology-output",
            str(output_layout_path),
            "--geom-output",
            str(output_geom_path),
            "--component",
            "P001",
            "--move",
            "0",
            "10",
            "0",
            "--run-id",
            "move-run",
            "--session-id",
            "session-move",
        ],
    )

    exit_code = layout_safe_move.main()

    assert exit_code == 0
    manifest = json.loads(
        (registry_dir / "runs" / "move-run.json").read_text(encoding="utf-8")
    )
    assert manifest["operation"]["tool"] == "freecad-layout-safe-move"
    assert manifest["operation"]["status"] == "success"
    assert manifest["inputs"]["input_layout_topology_path"] == str(layout_path)
    assert manifest["inputs"]["input_geom_path"] == str(geom_path)
    assert manifest["outputs"]["layout_topology_path"] == str(output_layout_path)
    assert manifest["outputs"]["geom_path"] == str(output_geom_path)
    assert Path(manifest["outputs"]["layout_topology_path"]).exists()
    assert Path(manifest["outputs"]["geom_path"]).exists()


def test_layout_safe_move_install_face_writes_rotation_matrix(
    monkeypatch, tmp_path: Path
) -> None:
    layout_path = tmp_path / "layout_topology.json"
    geom_path = tmp_path / "geom.json"
    output_layout_path = tmp_path / "layout_topology.updated.json"
    output_geom_path = tmp_path / "geom.updated.json"
    write_external_dataset(layout_path, geom_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-layout-safe-move",
            "--layout-topology",
            str(layout_path),
            "--geom",
            str(geom_path),
            "--layout-topology-output",
            str(output_layout_path),
            "--geom-output",
            str(output_geom_path),
            "--component",
            "P022",
            "--install-face",
            "10",
            "--move",
            "0",
            "0",
            "0",
        ],
    )

    exit_code = layout_safe_move.main()

    assert exit_code == 0
    updated_layout, updated_geom = load_layout_dataset_files(
        output_layout_path,
        output_geom_path,
    )
    normalized = normalize_layout_dataset(updated_layout, updated_geom)
    placement = normalized["components"]["P022"]["placement"]
    assert placement["mount_face"] == 10
    assert placement["rotation_matrix"] != [[1, 0, 0], [0, 1, 0], [0, 0, 1]]


def test_sync_layout_result_to_cad_sends_source_pose(
    monkeypatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_execute_batch_sync(host, port, doc_name, updates, **kwargs):
        captured["updates"] = updates
        captured["kwargs"] = kwargs
        return {"success": True, "document": doc_name}

    monkeypatch.setattr(
        layout_safe_move,
        "execute_batch_sync",
        fake_execute_batch_sync,
    )
    layout_path = tmp_path / "layout_topology.json"
    geom_path = tmp_path / "geom.json"
    args = SimpleNamespace(
        sync_cad=True,
        doc_name="DemoDoc",
        step_output=None,
        host="localhost",
        port=9876,
        component_object=None,
        part_object=None,
        component="P022",
    )
    source_component = {
        "shape": "box",
        "dims": [10.0, 20.0, 30.0],
        "placement": {
            "position": [1.0, 2.0, 55.0],
            "mount_face": 11,
        },
    }
    updated_component = {
        "shape": "box",
        "dims": [10.0, 20.0, 30.0],
        "placement": {
            "position": [55.0, -10.0, 5.0],
            "mount_face": 7,
            "rotation_matrix": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        },
    }

    payload = layout_safe_move.sync_layout_result_to_cad(
        args,
        layout_path,
        geom_path,
        "P022",
        updated_component,
        source_component=source_component,
    )

    assert payload["enabled"] is True
    assert payload["layout_topology_path"] == str(layout_path)
    assert payload["geom_path"] == str(geom_path)
    update = captured["updates"][0]
    assert update["source_position"] == [1.0, 2.0, 55.0]
    assert update["source_rotation_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert update["position"] == [55.0, -10.0, 5.0]
    assert update["rotation_matrix"] == [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]


def test_layout_safe_move_records_partial_success_when_cad_sync_fails(
    monkeypatch, tmp_path: Path
) -> None:
    layout_path = tmp_path / "layout_topology.json"
    geom_path = tmp_path / "geom.json"
    output_layout_path = tmp_path / "layout_topology.updated.json"
    output_geom_path = tmp_path / "geom.updated.json"
    registry_dir = tmp_path / "registry"
    write_dataset(layout_path, geom_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setattr(
        layout_safe_move,
        "sync_layout_result_to_cad",
        lambda *args, **kwargs: {
            "enabled": True,
            "success": False,
            "error": "sync failed",
            "document": "DemoDoc",
            "component": "P001",
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-layout-safe-move",
            "--layout-topology",
            str(layout_path),
            "--geom",
            str(geom_path),
            "--layout-topology-output",
            str(output_layout_path),
            "--geom-output",
            str(output_geom_path),
            "--component",
            "P001",
            "--move",
            "0",
            "10",
            "0",
            "--sync-cad",
            "--doc-name",
            "DemoDoc",
            "--run-id",
            "move-partial-run",
        ],
    )

    exit_code = layout_safe_move.main()

    assert exit_code == 2
    manifest = json.loads(
        (registry_dir / "runs" / "move-partial-run.json").read_text(encoding="utf-8")
    )
    assert manifest["operation"]["status"] == "partial_success"
    assert manifest["error"]["code"] == "CAD_SYNC_FAILED"


def test_layout_safe_move_records_step_and_glb_outputs_on_sync_success(
    monkeypatch, tmp_path: Path
) -> None:
    layout_path = tmp_path / "layout_topology.json"
    geom_path = tmp_path / "geom.json"
    output_layout_path = tmp_path / "layout_topology.updated.json"
    output_geom_path = tmp_path / "geom.updated.json"
    registry_dir = tmp_path / "registry"
    step_path = tmp_path / "DemoDoc.step"
    glb_path = tmp_path / "DemoDoc.glb"
    write_dataset(layout_path, geom_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))

    def fake_sync(*args, **kwargs):
        step_path.write_text("step-data", encoding="utf-8")
        glb_path.write_text("glb-data", encoding="utf-8")
        return {
            "enabled": True,
            "success": True,
            "document": "DemoDoc",
            "component": "P001",
            "step_path": str(step_path),
            "glb_path": str(glb_path),
        }

    monkeypatch.setattr(layout_safe_move, "sync_layout_result_to_cad", fake_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-layout-safe-move",
            "--layout-topology",
            str(layout_path),
            "--geom",
            str(geom_path),
            "--layout-topology-output",
            str(output_layout_path),
            "--geom-output",
            str(output_geom_path),
            "--component",
            "P001",
            "--move",
            "0",
            "10",
            "0",
            "--sync-cad",
            "--doc-name",
            "DemoDoc",
            "--run-id",
            "move-sync-success-run",
        ],
    )

    exit_code = layout_safe_move.main()

    assert exit_code == 0
    manifest = json.loads(
        (registry_dir / "runs" / "move-sync-success-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["operation"]["status"] == "success"
    assert manifest["outputs"]["layout_topology_path"] == str(output_layout_path)
    assert manifest["outputs"]["geom_path"] == str(output_geom_path)
    assert manifest["outputs"]["step_path"] == str(step_path)
    assert manifest["outputs"]["glb_path"] == str(glb_path)
    assert Path(manifest["outputs"]["step_path"]).exists()
    assert Path(manifest["outputs"]["glb_path"]).exists()


def test_layout_safe_move_records_partial_success_when_glb_export_missing(
    monkeypatch, tmp_path: Path
) -> None:
    layout_path = tmp_path / "layout_topology.json"
    geom_path = tmp_path / "geom.json"
    output_layout_path = tmp_path / "layout_topology.updated.json"
    output_geom_path = tmp_path / "geom.updated.json"
    registry_dir = tmp_path / "registry"
    step_path = tmp_path / "DemoDoc.step"
    glb_path = tmp_path / "DemoDoc.glb"
    write_dataset(layout_path, geom_path)
    monkeypatch.setenv("FREECAD_ARTIFACT_REGISTRY_DIR", str(registry_dir))

    def fake_sync(*args, **kwargs):
        step_path.write_text("step-data", encoding="utf-8")
        return {
            "enabled": True,
            "success": True,
            "document": "DemoDoc",
            "component": "P001",
            "step_path": str(step_path),
            "glb_path": str(glb_path),
        }

    monkeypatch.setattr(layout_safe_move, "sync_layout_result_to_cad", fake_sync)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "freecad-layout-safe-move",
            "--layout-topology",
            str(layout_path),
            "--geom",
            str(geom_path),
            "--layout-topology-output",
            str(output_layout_path),
            "--geom-output",
            str(output_geom_path),
            "--component",
            "P001",
            "--move",
            "0",
            "10",
            "0",
            "--sync-cad",
            "--doc-name",
            "DemoDoc",
            "--run-id",
            "move-glb-missing-run",
        ],
    )

    exit_code = layout_safe_move.main()

    assert exit_code == 2
    manifest = json.loads(
        (registry_dir / "runs" / "move-glb-missing-run.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["operation"]["status"] == "partial_success"
    assert manifest["outputs"]["step_path"] == str(step_path)
    assert manifest["outputs"]["glb_path"] == str(glb_path)
    assert manifest["error"]["code"] == "GLB_EXPORT_INCOMPLETE"
