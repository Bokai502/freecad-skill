# FreeCAD CLI Tools

用于操作 FreeCAD 文档、布局数据集以及直接装配构建工作流的命令行工具集合。
该包同时包含基于 XML-RPC 的命令和离线数据集工具。

英文版说明见 [README.md](./README.md)。

## 安装

### 方式一：从源码安装

```bash
cd /data/lbk/freecad_skills/freecad-skill/freecad_cli_tools
python -m pip install -e .
```

### 方式二：构建并安装 wheel

```bash
cd /data/lbk/freecad_skills/freecad-skill/freecad_cli_tools
python -m pip install build
python -m build
python -m pip install dist/freecad_cli_tools-*.whl
```

## 使用方式

安装完成后，所有命令都可以直接使用：

```bash
# 文档操作
freecad-create-doc "MyDocument"
freecad-list-docs

# 对象操作
freecad-create-obj "MyDoc" "Part::Box" "Box1" -p '{"Length": 100}'
freecad-edit-obj "MyDoc" "Box1" '{"Length": 200}'
freecad-del-obj "MyDoc" "Box1"
freecad-get-objs "MyDoc"
freecad-get-obj "MyDoc" "Box1"

# 零件库操作
freecad-get-parts
freecad-insert-part "Fasteners/Screws/M6x20.FCStd"

# 代码执行和视图
freecad-exec-code "import FreeCAD; print(FreeCAD.ActiveDocument.Name)"
freecad-get-view Isometric --output table.png
freecad-create-assembly --doc-name LayoutAssembly
freecad-create-assembly-from-component-info --doc-name DirectAssembly

# 基于 layout dataset 的安全移动与可选 CAD 同步
freecad-layout-safe-move --component P001 --move 50 50 0
freecad-layout-safe-move --component P001 --move 50 50 0 --sync-cad --doc-name LayoutAssembly
freecad-layout-safe-move --component P002 --install-face 4 --move 0 0 0
freecad-sync-placements --doc-name LayoutAssembly --updates-file updates.json

# 仅针对现有文档的兜底命令
freecad-check-collision "MyDoc" "P001_part" --move 0 0 -10
freecad-move-obj "MyDoc" "P001_part" 0 0 -10 --mode delta
```

默认情况下，相对 CLI 路径会基于运行时配置或环境变量中的
`FREECAD_WORKSPACE_DIR` 解析。
`freecad-create-assembly` 会读取 `./01_layout/layout_topology.json` 和
`./01_layout/geom.json`，并输出 `./02_geometry_edit/geometry_after.step`
及同名 `geometry_after.glb`。

`freecad-create-assembly-from-component-info` 会读取
`./01_layout/layout_topology.json`、`./01_layout/geom.json` 和
`./01_layout/geom_component_info.json`，优先从
`display_info.assets.cad_rotated_path` 导入真实 STEP/STP；缺失或不可读时
回退为 `Part::Box`。超过 `--max-step-size-mb` 的 STEP/STP 也会回退为
`Part::Box`，传 `-1` 可以关闭这个限制。这个直接构建流程同样输出
`./02_geometry_edit/geometry_after.step` 和同名 `geometry_after.glb`。

## 推荐移动流程

只要你手头有 `layout_topology.json` 和 `geom.json`，就建议把这对数据集作为单一事实来源：

1. 先运行 `freecad-layout-safe-move`。
2. 让它计算安全移动并把新的数据集写到 `./02_geometry_edit`。
3. 如果需要同步 CAD，就附加 `--sync-cad --doc-name <doc>`，同一条命令会更新 FreeCAD 文档。
4. 只有在你明确需要重新生成 CAD 文档时，才运行 `freecad-create-assembly`。

如果没有数据集来源，再把 `freecad-check-collision` 和 `freecad-move-obj` 当作文档级兜底命令使用。

## Layout Dataset 离线移动命令

`freecad-layout-safe-move` 是面向布局数据集的主移动命令。它既可以离线处理数据集，也可以把批准后的结果同步到正在运行的 FreeCAD 文档里。

在 `skills_test` 工作区流程中，移动和旋转请求默认会从 `./01_layout`
读取输入，并把新的数据集、`geometry_after.step`、`geometry_after.glb`
写到 `./02_geometry_edit`；只有在用户明确要求时，才覆盖原路径或指定其他输出。

适用场景包括：

- 在 `layout_topology.json + geom.json` 中移动单个组件
- 检测该组件与其它组件之间的盒体碰撞
- 在移动时保持当前朝向，或显式将组件重定向安装到另一个包络面
- 保证组件始终位于 `envelope.inner_size` 内
- 让外部安装面（6-11）的移动继续受目标墙面二维边界约束，若请求路径越界则返回 `FACE_BOUNDARY`
- 将新的位置和安装信息反写到 `layout_topology.json` 与 `geom.json`
- 可选地把更新后的结果同步到打开中的 FreeCAD 文档

如果你要根据布局数据集重建一个新的 CAD 文档，可以使用：

```bash
freecad-create-assembly \
  --doc-name LayoutAssembly
```

该命令会创建：

- 一个 `Assembly` 容器
- 当归一化后的数据集中存在 `envelope` 时，创建 `Envelope_part` 和 `EnvelopeShell`
- 每个组件对应一个 `App::Part` 和一个几何实体（当前支持 `Part::Box` / `Part::Cylinder`）
- 一套占位装配导出：`.step` 和同名 `.glb`
- 生成后自动做一次 GUI 视图拟合

该命令把 `placement.position` 视为组件局部包围盒最小角点位置，并默认在当前朝向下执行安全碰撞移动。在当前归一化模型里：

- `placement.mount_face` 表示组件安装到的包络面（`0..11`）
- `placement.rotation_matrix` 表示装配朝向

当传入 `--install-face` 时，命令会把组件旋转到“原组件接触面安装到目标包络面”的姿态，从目标面的中心位置开始，再把请求的移动量当作该安装面内的偏移量来执行。如果完整请求安全，就直接采用；如果不安全，就选择这条路径上的最近安全前缀；如果请求路径上没有安全点，命令会报告“未找到解”，但仍会写出受约束后的数据集结果。传入 `--sync-cad` 时，它会把最终计算出的位姿直接同步到目标 FreeCAD 文档里的对应对象。

补充说明：外部安装面（6-11）虽然会跳过内部包络包含约束，但仍会使用 `envelope.outer_size` 检查目标墙面的面内边界，避免组件沿墙面滑出边缘。如果请求路径跨出了这个二维轮廓，命令会截断到最近安全前缀，并在阻塞原因中包含 `FACE_BOUNDARY`。

运行时默认值按以下顺序解析：`FREECAD_RUNTIME_CONFIG`、项目内
`.freecad/freecad_runtime.conf`、项目内 `freecad_runtime.conf`、用户级
`~/.config/freecad-cli-tools/runtime.conf`，最后才使用兼容兜底的
[../config/freecad_runtime.conf](../config/freecad_runtime.conf)。

对于多组件位姿更新，`freecad-sync-placements` 接受如下 JSON 列表：

```json
[
  {
    "component": "P006",
    "position": [-103.72, 139.72, -170.91],
    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  },
  {
    "component": "P018",
    "position": [-249.72, 179.32, -170.91],
    "rotation_matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
  }
]
```

## 开发布局

- `src/freecad_cli_tools/cli/`：轻量级命令入口
- `src/freecad_cli_tools/geometry.py`：纯几何运算、碰撞检测和组件形状辅助函数（无外部依赖）
- `src/freecad_cli_tools/layout_dataset.py`：layout dataset 归一化与反写
- `src/freecad_cli_tools/layout_dataset_common.py`：layout dataset 共享校验辅助函数
- `src/freecad_cli_tools/layout_dataset_faces.py`：安装面映射与反向解析
- `src/freecad_cli_tools/layout_dataset_io.py`：layout dataset 原子 JSON I/O
- `src/freecad_cli_tools/component_info_assembly.py`：基于 `geom_component_info.json` 的直接装配归一化逻辑
- `src/freecad_cli_tools/freecad_sync.py`：单组件和批量组件的位姿同步辅助逻辑
- `src/freecad_cli_tools/cli_support.py`：CLI 侧共享工具，例如 RPC 调用、输出解析和文件输入
- `src/freecad_cli_tools/rpc_scripts/`：通过 XML-RPC 在 FreeCAD 侧执行的 Python 脚本
- `src/freecad_cli_tools/rpc_script_loader.py`：打包脚本加载和占位符渲染
- `src/freecad_cli_tools/rpc_script_fragments.py`：可注入脚本模板的 FreeCAD 侧公共代码片段
- `tests/`：几何算法、格式校验、片段同步验证和 RPC 模板语法的单元测试

## 依赖要求

- 对于 RPC 命令：需要安装并运行带 MCP 插件的 FreeCAD，RPC 服务使用运行时配置或环境变量中的主机和端口
- 相对输入输出路径会基于运行时配置或环境变量中的 `FREECAD_WORKSPACE_DIR` 解析
- 对于离线 layout dataset 模式的 `freecad-layout-safe-move`：只需要 Python 3.9+
- Python 3.9+

## 许可证

MIT
