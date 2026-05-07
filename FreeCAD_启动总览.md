# FreeCAD 启动总览

## 当前主流程

当前工作区已经切换为 Linux 本机直连 FreeCAD，不再依赖 WSL、WSLg 或仓库内启动脚本。

推荐流程：

1. 直接在 Linux 环境启动 `freecad`
2. 确认 `FreeCADMCP` 插件已经自动启动 XML-RPC 服务
3. 使用 `freecad-*` CLI 命令连接 RPC 地址，并显式传入工作区

## 前提条件

- Linux 环境里已经安装 `freecad`
- FreeCAD 已安装 `FreeCADMCP` 插件
- 运行 CLI 前需要显式提供工作区

## 常用命令

### 启动 FreeCAD

```bash
freecad
```

### 检查 RPC

```bash
freecad-list-docs
freecad-validate-workspace --workspace /abs/path/to/workspace
freecad-create-assembly --workspace /abs/path/to/workspace --doc-name LayoutAssembly
```

## 配置

工作区只允许两种来源：

1. CLI 参数 `--workspace /abs/path/to/workspace`
2. 环境变量 `FREECAD_WORKSPACE_DIR=/abs/path/to/workspace`

常用配置项：

- `FREECAD_RPC_HOST`
- `FREECAD_RPC_PORT`
- `FREECAD_WORKSPACE_DIR`

## 结论

如果你只想记住一个入口，就记这个：

```bash
export FREECAD_WORKSPACE_DIR=/abs/path/to/workspace
freecad
```
