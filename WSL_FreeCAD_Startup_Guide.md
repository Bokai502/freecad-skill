# WSL FreeCAD 启动指南

## 1. 这份文档解决什么问题

这台机器上的 FreeCAD 不是直接跑在 Windows 本地，而是主要跑在 `WSL2` 的 `Ubuntu-24.04` 里。

当前推荐链路是：

1. 在 WSL 中启动 FreeCAD
2. 让 `FreeCADMCP` 自动启动 XML-RPC 服务
3. 在 Windows 侧使用 `freecad-*` CLI 命令访问 RPC

默认 RPC 端口是：

- `9875`

## 2. 当前目录约定

工作目录：`D:\workspace\skills_test`

当前约定如下：

- `scripts/`
  - 放启动脚本和辅助脚本
- `data/`
  - 放 YAML、`FCStd`、截图等数据文件
- `freecad_cli_tools/`
  - 放 CLI 工具源码
- `skill_backups/`
  - 放 skill 备份

本指南里提到的关键文件：

- [`scripts/start_wsl_freecad_rpc.ps1`](scripts/start_wsl_freecad_rpc.ps1)
- [`scripts/start_freecad_rpc_xvfb_wsl.sh`](scripts/start_freecad_rpc_xvfb_wsl.sh)
- [`scripts/start_freecad_rpc_wsl.sh`](scripts/start_freecad_rpc_wsl.sh)
- [`scripts/freecad_direct_xvfb_wsl.sh`](scripts/freecad_direct_xvfb_wsl.sh)

## 3. 推荐启动方式

### 3.1 Windows 一键启动 RPC

这是当前最推荐的方式。

在 Windows PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1
```

这个脚本会：

- 进入 `Ubuntu-24.04`
- 调用 `scripts/start_freecad_rpc_xvfb_wsl.sh`
- 启动无头 FreeCAD
- 等待 RPC 端口 `9875` 可用
- 输出关键日志

### 3.2 直接调用 WSL 启动脚本

如果你不想经过 `.ps1` 包装脚本，也可以直接运行：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'cp /mnt/d/workspace/skills_test/scripts/start_freecad_rpc_xvfb_wsl.sh /root/start_freecad_rpc_xvfb.sh; chmod +x /root/start_freecad_rpc_xvfb.sh; /root/start_freecad_rpc_xvfb.sh'
```

这和上一节本质上是同一条链路，只是少了 Windows 侧的包装。

## 4. 各脚本的作用

### `scripts/start_wsl_freecad_rpc.ps1`

定位：

- Windows 入口脚本

用途：

- 适合平时在 Windows 里一键启动 WSL 内的 RPC 服务

推荐程度：

- 高

### `scripts/start_freecad_rpc_xvfb_wsl.sh`

定位：

- 当前主启动脚本

用途：

- 先清理旧进程
- 激活 WSL 中的 `freecad` conda 环境
- 在 `Xvfb` 下启动无头 FreeCAD
- 等待 `9875` 端口监听
- 打印启动日志和 FreeCAD 日志

推荐程度：

- 最高

### `scripts/start_freecad_rpc_wsl.sh`

定位：

- 旧版简化脚本

用途：

- 也能启动 WSL 内的 FreeCAD 和 Xvfb

问题：

- 启动链路更简单
- 没有当前主脚本稳定
- 不建议作为默认入口

推荐程度：

- 低，仅作备用

### `scripts/freecad_direct_xvfb_wsl.sh`

定位：

- 调试脚本

用途：

- 直接以前台方式运行 `xvfb-run freecad`
- 适合手动排查 GUI / Xvfb / Qt 问题

推荐程度：

- 中，仅用于调试

## 5. 如何确认 RPC 已经启动

在 Windows PowerShell 里执行：

```powershell
Test-NetConnection -ComputerName localhost -Port 9875
```

如果启动正常，通常会看到：

```text
TcpTestSucceeded : True
```

也可以直接用 CLI 验证：

```powershell
freecad-list-docs
freecad-exec-code "import FreeCAD; print('rpc-ok')"
```

## 6. 如何打开 GUI 窗口

如果你想看到 FreeCAD 的可视化窗口，不要继续使用无头 RPC 脚本，而应该改走 `WSLg` GUI 模式。

先停掉无头模式：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'pkill -x freecad || true; pkill -x Xvfb || true'
```

然后启动 GUI：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'source /root/miniconda3/etc/profile.d/conda.sh; conda activate freecad; freecad'
```

如果要用一条命令同时“停掉无头 + 打开 GUI”，可以直接运行：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'pkill -x freecad || true; pkill -x Xvfb || true; source /root/miniconda3/etc/profile.d/conda.sh; conda activate freecad; freecad'
```

## 7. 停止 FreeCAD

停止 WSL 里的 FreeCAD 和 Xvfb：

```powershell
wsl -d Ubuntu-24.04 -- bash -lc 'pkill -x freecad || true; pkill -x Xvfb || true'
```

## 8. 常见工作流

### 8.1 做自动化、跑 CLI、同步 CAD

推荐：

1. 启动 RPC
2. 验证 `9875`
3. 执行 `freecad-*` 命令

示例：

```powershell
powershell -ExecutionPolicy Bypass -File D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1
freecad-create-assembly --input D:\workspace\skills_test\data\sample.yaml --doc-name SampleYamlAssembly
```

### 8.2 做人工查看、交互操作

推荐：

1. 停掉无头 FreeCAD
2. 通过 `WSLg` 启动 GUI
3. 在 Windows 桌面直接操作 FreeCAD

## 9. 常见问题排查

### 9.1 RPC 端口没有起来

先重新运行推荐启动脚本，然后查看日志：

```powershell
wsl -d Ubuntu-24.04 -- sed -n 1,200p /tmp/freecad-launch.log
wsl -d Ubuntu-24.04 -- sed -n 1,200p /tmp/freecad-rpc.log
```

### 9.2 Windows 侧连不上 `localhost:9875`

先查看当前 WSL IP：

```powershell
wsl -d Ubuntu-24.04 -- hostname -I
```

然后临时指定环境变量：

```powershell
$env:FREECAD_RPC_HOST='你的_WSL_IP'
$env:FREECAD_RPC_PORT='9875'
freecad-list-docs
```

### 9.3 GUI 没有弹出

常见原因：

- `WSLg` 当前不可用
- 无头 `Xvfb` 模式还没停掉
- Qt 平台插件有问题

建议顺序：

1. 先执行停止命令
2. 再执行 GUI 启动命令
3. 如果还不行，再看 WSL 内日志和终端报错

## 10. 建议记住的唯一入口

如果你只想记住一条“启动当前这套环境”的命令，就记这个：

```powershell
powershell -ExecutionPolicy Bypass -File D:\workspace\skills_test\scripts\start_wsl_freecad_rpc.ps1
```

这是当前最适合作为日常默认入口的启动方式。
