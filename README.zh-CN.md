# Skills Test 工作区说明

`skills_test` 是一个面向 FreeCAD 的工作区，用于基于布局数据集的装配生成、带碰撞约束的组件移动，以及通过 XML-RPC 进行 CAD 同步。

## 工作区包含的内容

- `freecad_cli_tools/`：Python 工具包，提供 FreeCAD CLI 命令、YAML 安全移动逻辑、RPC 辅助模块、测试和包级文档。
- `01_layout/`：被版本控制跟踪的布局数据集输入目录。
- `02_geometry_edit/`：生成的几何编辑输出目录，例如 `geometry_after.step` 和验证结果文件。
- `data/`：运行期输出目录，例如生成的 STEP、更新后的 YAML、截图以及临时验证文件。该目录默认被 git 忽略。
- `skill_backups/`：当前 FreeCAD skill 指令的本地备份。

## 核心能力

- 通过本机 Linux 上正在运行的 FreeCAD MCP/XML-RPC 服务执行 CLI 操作。
- 根据 `layout_topology.json + geom.json` 创建 FreeCAD 装配。
- 基于 `layout_topology.json + geom.json` 导出占位装配。
- 基于 `layout_topology.json + geom.json + geom_component_info.json` 直接导出真实 CAD 或 box 回退装配。
- 在内部包络、外部安装面边界和碰撞约束下安全移动组件。
- 将一个或多个计算后的位姿同步到正在运行的 FreeCAD 文档。
- 通过测试、CI 和基准脚本验证功能与性能。

## 快速开始

### 1. 启动 FreeCAD RPC 服务

```bash
freecad
```

请确保已安装 FreeCADMCP 插件，并且 XML-RPC 服务已启动。运行时默认值来自
`FREECAD_RUNTIME_CONFIG`、项目内 `.freecad/freecad_runtime.conf`、用户级
`~/.config/freecad-cli-tools/runtime.conf`，或作为兼容兜底的
[config/freecad_runtime.conf](./config/freecad_runtime.conf)。

### 2. 安装 CLI 工具包

```bash
python -m pip install -e ./freecad_cli_tools[dev]
```

### 3. 根据布局数据集创建装配

```powershell
freecad-create-assembly --doc-name LayoutAssembly
```

或者直接根据 component info 构建一个全新的装配：

```powershell
freecad-create-assembly-from-component-info --doc-name DirectAssembly
```

### 4. 执行一次安全移动并同步回 CAD

```powershell
freecad-layout-safe-move --component P005 --install-face 5 --move 228.83671815191935 195.70657882164386 0 --sync-cad --doc-name LayoutAssembly
```

对于外部安装面，同一条命令会以 `envelope.outer_size` 作为墙面参考，让组件保持在壳体外侧，
同时继续约束它只能在目标安装面的二维边界内移动，避免沿墙面滑出边缘。

在当前工作区的 skill 流程中，CLI 相对路径会基于运行时配置或环境变量里的
`FREECAD_WORKSPACE_DIR` 解析。默认从 `./01_layout` 读取源输入，并把
新的数据集、STEP、GLB 输出到 `./02_geometry_edit`，统一使用
`geometry_after` 作为文件名前缀，因此不会修改原始文件。

当 `./01_layout/geom_component_info.json` 存在时，
`freecad-create-assembly-from-component-info` 会把它与
`layout_topology.json`、`geom.json` 一起使用，优先读取
`display_info.assets.cad_rotated_path` 指向的 STEP；若 STEP 缺失、不可用，
或超过 `--max-step-size-mb`，则回退为 box，并输出
`geometry_after.step` 和同名 `geometry_after.glb`。

### 5. 批量同步多个位姿

```powershell
freecad-sync-placements --doc-name LayoutAssembly --updates-file updates.json
```

## 文档导航

- 英文版本更新记录：[VERSION_UPDATES.md](./VERSION_UPDATES.md)
- 中文版本更新记录：[VERSION_UPDATES.zh-CN.md](./VERSION_UPDATES.zh-CN.md)
- 工具包说明（英文）：[freecad_cli_tools/README.md](./freecad_cli_tools/README.md)
- 工具包说明（中文）：[freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md)
- 系统架构与流程图：[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)
- FreeCADMCP 兼容补丁：[docs/FREECADMCP_QT_COMPAT_PATCH.zh-CN.md](./docs/FREECADMCP_QT_COMPAT_PATCH.zh-CN.md)
- 启动相关说明：[FreeCAD_启动总览.md](./FreeCAD_启动总览.md)

## 工作区结构

```text
skills_test/
|-- freecad_cli_tools/      # CLI 工具包、RPC 辅助模块、测试
|-- 01_layout/             # 被跟踪的布局数据集输入
|-- 02_geometry_edit/      # 生成的几何编辑输出
|-- data/                  # 其他运行期输出，git 忽略
|-- docs/                   # 架构图与流程图
|-- skill_backups/          # 最新 FreeCAD skill 备份
|-- VERSION_UPDATES.md
\-- README.zh-CN.md
```

## 建议阅读顺序

1. 先读本文件，了解工作区整体结构。
2. 再读 [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)，了解系统构成与主流程。
3. 然后读 [freecad_cli_tools/README.md](./freecad_cli_tools/README.md) 或 [freecad_cli_tools/README.zh-CN.md](./freecad_cli_tools/README.zh-CN.md)，查看 CLI 使用细节。
4. 最后读 [VERSION_UPDATES.zh-CN.md](./VERSION_UPDATES.zh-CN.md)，了解历史变化与性能演进。
