# FreeCAD 启动总览

## 当前目录结构

- `scripts/`
  - 放启动和辅助脚本
- `data/`
  - 放 YAML、`STEP`、截图等数据文件
- `freecad_cli_tools/`
  - 放 CLI 工具源码
- `skill_backups/`
  - 放 skill 备份

## 当前推荐启动方式

当前主流程是：

1. 在 Windows 里启动 WSL 内的 FreeCAD
2. 由 WSL 内的 `FreeCADMCP` 自动拉起 XML-RPC 服务
3. 在 Windows 侧使用 `freecad-*` CLI 连接 `9875` 端口

推荐入口：

- Windows 包装脚本：[`scripts/start_wsl_freecad_rpc.ps1`](scripts/start_wsl_freecad_rpc.ps1)
- WSL 实际启动脚本：[`scripts/start_freecad_rpc_xvfb_wsl.sh`](scripts/start_freecad_rpc_xvfb_wsl.sh)

## 各启动脚本的作用

### `scripts/start_wsl_freecad_rpc.ps1`

推荐保留并优先使用。

作用：

- 在 Windows PowerShell 中一键启动
- 调用 WSL 中的 `start_freecad_rpc_xvfb_wsl.sh`
- 适合作为日常“启动 RPC 服务”的入口

### `scripts/start_freecad_rpc_xvfb_wsl.sh`

这是当前最重要的启动脚本。

作用：

- 停掉旧的 `freecad` / `Xvfb`
- 激活 WSL 中的 `freecad` conda 环境
- 用 `xvfb-run` 启动无头 FreeCAD
- 等待 `9875` 端口可用
- 输出日志，方便排障

适用场景：

- Codex/CLI 自动化
- YAML -> CAD 同步
- 稳定的无头 RPC 服务

### `scripts/start_freecad_rpc_wsl.sh`

这是旧版简化脚本，建议保留为备用，不建议作为主入口。

原因：

- 它的启动流程更简单
- 没有现在这版完整的清理、等待和日志处理
- 稳定性不如 `start_freecad_rpc_xvfb_wsl.sh`

### `scripts/freecad_direct_xvfb_wsl.sh`

更适合手动调试。

作用：

- 直接以前台方式在 `xvfb-run` 下启动 FreeCAD
- 适合观察启动行为
- 不适合日常后台 RPC 启动

## GUI 模式说明

如果你要在 Windows 桌面直接看到 FreeCAD 窗口，应该走 `WSLg` GUI 模式，而不是上面的无头 RPC 模式。

典型命令：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'pkill -x freecad || true; pkill -x Xvfb || true; source /root/miniconda3/etc/profile.d/conda.sh; conda activate freecad; freecad'
```

## 常用命令

### 启动 RPC

```powershell
powershell -ExecutionPolicy Bypass -File D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1
```

### 检查 RPC

```powershell
freecad-list-docs
freecad-exec-code "import FreeCAD; print('rpc-ok')"
```

### 从 YAML 生成装配

```powershell
freecad-create-assembly --input D:\workspace\skills_test\data\sample.yaml --doc-name SampleYamlAssembly
```

### 停止 WSL 中的 FreeCAD

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'pkill -x freecad || true; pkill -x Xvfb || true'
```

## 结论

如果你只想记一个入口，就记这个：

```powershell
powershell -ExecutionPolicy Bypass -File D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1
```

它是当前这套环境里最适合作为日常启动入口的方式。
