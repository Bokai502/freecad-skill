# Skills Test 工作区说明

`skills_test` 是一个面向 FreeCAD 的工作区，用于基于 YAML 的装配生成、带碰撞约束的组件移动，以及通过 XML-RPC 进行 CAD 同步。

## 工作区包含的内容

- `freecad_cli_tools/`：Python 工具包，提供 FreeCAD CLI 命令、YAML 安全移动逻辑、RPC 辅助模块、测试和包级文档。
- `examples/`：被版本控制跟踪的示例输入文件，例如 [sample.yaml](./examples/sample.yaml)。
- `data/`：运行期输出目录，例如生成的 STEP、更新后的 YAML、截图以及临时验证文件。该目录默认被 git 忽略。
- `skill_backups/`：当前 FreeCAD skill 指令的本地备份。

## 核心能力

- 通过本机 Linux 上正在运行的 FreeCAD MCP/XML-RPC 服务执行 CLI 操作。
- 根据 YAML 定义创建 FreeCAD 装配。
- 在内部包络、外部安装面边界和碰撞约束下安全移动组件。
- 将一个或多个计算后的位姿同步到正在运行的 FreeCAD 文档。
- 通过测试、CI 和基准脚本验证功能与性能。

## 快速开始

### 1. 启动 FreeCAD RPC 服务

```bash
freecad
```

请确保已安装 FreeCADMCP 插件，并且 XML-RPC 服务使用 [config/freecad_runtime.conf](./config/freecad_runtime.conf) 中配置的主机和端口启动（当前为 `localhost:9876`）。

### 2. 安装 CLI 工具包

```bash
python -m pip install -e ./freecad_cli_tools[dev]
```

### 3. 根据 YAML 创建装配

```powershell
freecad-create-assembly --input examples\sample.yaml --doc-name SampleYamlAssembly
```

### 4. 执行一次安全移动并同步回 CAD

```powershell
freecad-yaml-safe-move --input examples\sample.yaml --output examples\sample.yaml --component P005 --install-face 5 --move 228.83671815191935 195.70657882164386 0 --sync-cad --doc-name SampleYamlAssembly
```

对于外部安装面，同一条命令会以 `envelope.outer_size` 作为墙面参考，让组件保持在壳体外侧，
同时继续约束它只能在目标安装面的二维边界内移动，避免沿墙面滑出边缘。

在当前工作区的 skill 流程中，移动和旋转操作默认会原地更新 YAML，并将当前 `STEP` 文件原地重新导出，而不是默认再生成旁路输出文件。

### 5. 批量同步多个位姿

```powershell
freecad-sync-placements --doc-name SampleYamlAssembly --updates-file updates.json
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
|-- examples/               # 被跟踪的示例输入
|-- data/                   # 运行期输出，git 忽略
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
