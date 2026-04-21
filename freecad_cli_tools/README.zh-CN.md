# FreeCAD CLI Tools

用于操作 FreeCAD 文档以及相关 YAML 布局文件的命令行工具集合。该包同时包含基于 XML-RPC 的命令和离线 YAML 工具。

英文版说明见 [README.md](./README.md)。

## 安装

### 方式一：从源码安装

```bash
cd D:\workspace\skills_test\freecad_cli_tools
conda run -n base pip install -e .
```

### 方式二：构建并安装 wheel

```bash
cd D:\workspace\skills_test\freecad_cli_tools
conda run -n base pip install build
conda run -n base python -m build
conda run -n base pip install dist/freecad_cli_tools-*.whl
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
freecad-create-assembly --input examples/sample.yaml --doc-name SampleYamlAssembly

# 基于 YAML 的安全移动与可选 CAD 同步
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P001 --move 50 50 0
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P001 --move 50 50 0 --sync-cad --doc-name SampleYamlAssembly
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P002 --install-face 4 --move 0 0 0
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P021 --install-face 9 --move 60 0 0
freecad-yaml-safe-move --input examples/sample.yaml --output examples/sample.yaml --component P002 --spin 90 --move 0 0 0
freecad-sync-placements --doc-name SampleYamlAssembly --updates-file updates.json

# 仅针对现有文档的兜底命令
freecad-check-collision "MyDoc" "P001_part" --move 0 0 -10
freecad-move-obj "MyDoc" "P001_part" 0 0 -10 --mode delta
```

## 推荐移动流程

只要你手头有 YAML 配置文件，就建议把 YAML 作为单一事实来源：

1. 先对 YAML 运行 `freecad-yaml-safe-move`。
2. 让它计算安全移动并写出更新后的 YAML。
3. 如果需要同步 CAD，就附加 `--sync-cad --doc-name <doc>`，同一条命令会更新 FreeCAD 文档。
4. 只有在你明确需要重新生成 CAD 文档时，才运行 `freecad-create-assembly`。

如果没有 YAML 来源，再把 `freecad-check-collision` 和 `freecad-move-obj` 当作文档级兜底命令使用。

## YAML 离线移动命令

`freecad-yaml-safe-move` 是面向 YAML 的主移动命令。它既可以离线处理 YAML，也可以把批准后的结果同步到正在运行的 FreeCAD 文档里。

在 `skills_test` 工作区流程中，移动和旋转请求默认会覆盖源 YAML，并在同步后把现有 `STEP` 文件原地重新导出；只有在用户明确要求时，才额外产出新的重建文件。

适用场景包括：

- 在 YAML 装配定义中移动单个组件
- 检测该组件与其它组件之间的盒体碰撞
- 在移动时保持当前朝向，或显式将组件重定向安装到另一个包络面
- 保证组件始终位于 `envelope.inner_size` 内
- 让外部安装面（6-11）的移动继续受目标墙面二维边界约束，若请求路径越界则返回 `FACE_BOUNDARY`
- 将新的位置、`mount_point`、`envelope_face` 和可选的 `rotation_matrix` 写回新的 YAML 文件
- 可选地把更新后的结果同步到打开中的 FreeCAD 文档

如果你要根据更新后的 YAML 重建一个新的 CAD 文档，可以使用：

```bash
freecad-create-assembly --input examples/sample.yaml --doc-name SampleYamlAssembly
```

该命令会创建：

- 一个 `Assembly` 容器
- 当 YAML 中存在 `envelope` 时，创建 `Envelope_part` 和 `EnvelopeShell`
- 每个组件对应一个 `App::Part` 和一个 `Part::Box`
- 生成后自动做一次 GUI 视图拟合

该命令把 `placement.position` 视为盒体最小角点位置，并默认在当前朝向下执行仅平移的安全碰撞移动。在当前 YAML / CLI 模型里：

- `placement.mount_face` 表示组件自身的安装面
- `placement.envelope_face` 表示组件安装到的包络面
- `placement.rotation_matrix` 表示装配朝向

当传入 `--install-face` 时，命令会把组件旋转到“自身 `mount_face` 安装到目标包络面”的姿态，从目标面的中心位置开始，再把请求的移动量当作该安装面内的偏移量来执行。如果完整请求安全，就直接采用；如果不安全，就选择这条路径上的最近安全前缀；如果请求路径上没有安全点，命令会报告“未找到解”，但仍会写出受约束后的 YAML 结果。传入 `--sync-cad` 时，它会把最终计算出的位姿直接同步到目标 FreeCAD 文档里的对应对象。

补充说明：外部安装面（6-11）虽然会跳过内部包络包含约束，但仍会使用 `envelope.outer_size` 检查目标墙面的面内边界，避免组件沿墙面滑出边缘。如果请求路径跨出了这个二维轮廓，命令会截断到最近安全前缀，并在阻塞原因中包含 `FACE_BOUNDARY`。

在当前这台机器上，FreeCAD 可能运行在 WSL 中，而 CLI 运行在 Windows 上。这种情况下：

- `--input` 和 `--output` 仍然使用普通 Windows 路径
- CLI 仍会把 YAML 结果写到磁盘，但 `--sync-cad` 不再要求 FreeCAD 重新打开该 YAML
- 如果 Windows 到 `localhost:9875` 的转发不稳定，可以传 `--host <当前 WSL IP> --port 9875`

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
- `src/freecad_cli_tools/yaml_schema.py`：YAML 装配格式校验，提供清晰的错误信息
- `src/freecad_cli_tools/freecad_sync.py`：单组件和批量组件的位姿同步辅助逻辑
- `src/freecad_cli_tools/cli_support.py`：CLI 侧共享工具，例如 RPC 调用、输出解析和文件输入
- `src/freecad_cli_tools/rpc_scripts/`：通过 XML-RPC 在 FreeCAD 侧执行的 Python 脚本
- `src/freecad_cli_tools/rpc_script_loader.py`：打包脚本加载和占位符渲染
- `src/freecad_cli_tools/rpc_script_fragments.py`：可注入脚本模板的 FreeCAD 侧公共代码片段
- `tests/`：几何算法、格式校验、片段同步验证和 RPC 模板语法的单元测试

## 依赖要求

- 对于 RPC 命令：需要安装并运行带 MCP 插件的 FreeCAD，RPC 服务默认监听 `localhost:9875`
- 对于离线 YAML 模式的 `freecad-yaml-safe-move`：只需要 Python 3.9+
- Python 3.9+

## 许可证

MIT
