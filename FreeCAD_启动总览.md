# FreeCAD 启动总览

## 当前主流程

当前工作区已经切换为 Linux 本机直连 FreeCAD，不再依赖 WSL、WSLg 或仓库内启动脚本。

推荐流程：

1. 直接在 Linux 环境启动 `freecad`
2. 确认 `FreeCADMCP` 插件已经自动启动 XML-RPC 服务
3. 使用 `freecad-*` CLI 命令连接运行时配置中的 RPC 地址

## 前提条件

- Linux 环境里已经安装 `freecad`
- FreeCAD 已安装 `FreeCADMCP` 插件
- RPC 服务默认监听运行时配置中的地址

## 常用命令

### 启动 FreeCAD

```bash
freecad
```

### 检查 RPC

```bash
freecad-list-docs
freecad-create-assembly --doc-name LayoutAssembly
```

## 配置

运行时默认值按以下顺序解析：

1. `FREECAD_RUNTIME_CONFIG`
2. 当前项目 `.freecad/freecad_runtime.conf`
3. 当前项目 `freecad_runtime.conf`
4. 用户级 `~/.config/freecad-cli-tools/runtime.conf`
5. 兼容兜底：[config/freecad_runtime.conf](./config/freecad_runtime.conf)

常用配置项：

- `FREECAD_RPC_HOST`
- `FREECAD_RPC_PORT`
- `FREECAD_WORKSPACE_DIR`

## 结论

如果你只想记住一个入口，就记这个：

```bash
freecad
```
