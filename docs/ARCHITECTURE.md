# System Architecture And Workflow / 系统架构与流程图

This document provides a visual overview of the `skills_test` workspace and the main FreeCAD automation flow.

本文档用于展示 `skills_test` 工作区的核心系统结构，以及 FreeCAD 自动化的主流程。

## System Architecture

```mermaid
flowchart LR
    U["User / Codex Request"]
    S["Workspace Scripts<br/>start_wsl_freecad_rpc.ps1<br/>start_freecad_gui_wsl.sh"]
    I["Tracked Inputs<br/>examples/sample.yaml<br/>updates.json"]
    C["CLI Layer<br/>freecad-create-assembly<br/>freecad-yaml-safe-move<br/>freecad-sync-placements"]
    H["Shared Helpers<br/>cli_support.py<br/>rpc_client.py<br/>freecad_sync.py"]
    R["Script Rendering<br/>rpc_script_loader.py<br/>rpc_script_fragments.py"]
    X["XML-RPC Channel"]
    F["FreeCAD Runtime In WSL/WSLg"]
    P["FreeCAD RPC Scripts<br/>assembly_from_yaml.py<br/>sync_component_placements.py<br/>check_document_collisions.py"]
    D["FreeCAD Documents<br/>GUI State<br/>Runtime Outputs In data/"]
    T["Quality Layer<br/>pytest<br/>ruff<br/>black<br/>GitHub Actions CI"]

    U --> S
    U --> I
    U --> C
    I --> C
    C --> H
    H --> R
    R --> X
    X --> F
    F --> P
    P --> D
    T --> C
    T --> H
```

## Main Safe-Move Workflow

```mermaid
flowchart TD
    A["Input Request<br/>YAML Path + Component + Move"] --> B["Load YAML Layout"]
    B --> C["Resolve Component State<br/>Mount Face<br/>Envelope Face<br/>Rotation"]
    C --> D["Build Analysis Context<br/>Envelope Bounds + Static Obstacles"]
    D --> E["Project Move Onto Target Mount Plane"]
    E --> F["Run Linear Safe-Prefix Search<br/>Collision + Boundary Checks"]
    F --> G{"Safe Full Move?"}
    G -- "Yes" --> H["Use Requested Target Position"]
    G -- "No" --> I["Use Closest Safe Prefix<br/>Or Constrained Fallback"]
    H --> J["Update YAML Placement<br/>position<br/>mount_point<br/>rotation_matrix"]
    I --> J
    J --> K["Overwrite Source YAML"]
    K --> L{"Sync CAD?"}
    L -- "No" --> M["Return Analysis And Updated YAML Path"]
    L -- "Yes" --> N["Normalize Placement Updates"]
    N --> O["Render Batch Sync RPC Script"]
    O --> P["Update One Or More Objects In FreeCAD"]
    P --> Q["Optional Single Recompute"]
    Q --> R["Re-export Existing STEP File"]
    R --> S["Return Final Result"]
```

## Move-Part Sequence Diagram

```mermaid
sequenceDiagram
    participant U as "User"
    participant K as "$freecad Skill"
    participant C as "freecad-yaml-safe-move"
    participant Y as "YAML Layout"
    participant S as "freecad_sync.py"
    participant X as "XML-RPC"
    participant F as "FreeCAD Runtime"
    participant R as "sync_component_placements.py"

    U->>K: Request move for one part
    K->>K: Route to safe-move-workflow
    K->>C: Invoke YAML-first safe move CLI
    C->>Y: Load component placement and envelope data
    C->>C: Compute safe target or closest safe prefix
    C->>Y: Overwrite source YAML with updated placement

    alt sync current CAD document
        C->>S: Build normalized placement update
        S->>X: Send rendered batch sync script
        X->>F: Execute RPC code
        F->>R: Apply Placement to solid/part
        R-->>F: Return sync payload
        F-->>X: Return JSON result
        X-->>S: Parsed payload
        S-->>C: Sync success/failure
        C->>F: Re-export current STEP file in place
    end

    C-->>K: Safe move result and updated file paths
    K-->>U: Report executed move and any adjustment
```

## Notes

- `examples/` stores tracked sample inputs.
- `data/` stores generated files and verification outputs, and is intentionally ignored by git.
- `freecad-yaml-safe-move` is the YAML-first path for collision-aware movement.
- `freecad-sync-placements` is the reusable batch placement path for faster multi-component updates.
- The current skill workflow overwrites the existing YAML and re-exports the existing `STEP` file in place for move/rotate requests.

## 中文说明

- `examples/` 用于保存被版本控制跟踪的示例输入。
- `data/` 用于保存运行期输出和验证产物，默认不进入 git。
- `freecad-yaml-safe-move` 是面向 YAML 的安全移动主路径。
- `freecad-sync-placements` 是面向多组件同步的批量更新路径。
