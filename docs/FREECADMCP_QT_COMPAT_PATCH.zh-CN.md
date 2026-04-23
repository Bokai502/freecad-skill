# FreeCADMCP Qt 兼容补丁

## 背景

在当前环境中：

- FreeCAD 版本为 `0.19`
- `FreeCADMCP` 插件安装在 `~/.FreeCAD/Mod/FreeCADMCP`
- 插件需要在 FreeCAD 启动后自动拉起 XML-RPC 服务，默认监听 `localhost:9876`

实际排查中发现，RPC 没有启动的根因不是端口未开放，而是插件在自动启动阶段报错：

```text
[MCP] Auto-start failed: cannot import name 'QtWidgets' from 'PySide'
```

这是因为当前 FreeCAD 0.19 暴露的 `PySide` 环境不提供 `QtWidgets`，而插件源码直接使用了：

```python
from PySide import QtCore, QtWidgets
```

导致 `InitGui.py` 中的自动启动逻辑在导入 `rpc_server` 时直接失败，`9876` 因而始终没有监听。

## 正式修复

需要修改的文件：

- `~/.FreeCAD/Mod/FreeCADMCP/rpc_server/rpc_server.py`

### 补丁内容

将：

```python
from PySide import QtCore, QtWidgets
```

替换为：

```python
try:
    from PySide import QtCore, QtWidgets
except ImportError:
    from PySide import QtCore, QtGui
    QtWidgets = QtGui
```

### 统一 diff

```diff
--- a/rpc_server.py
+++ b/rpc_server.py
@@
-from PySide import QtCore, QtWidgets
+try:
+    from PySide import QtCore, QtWidgets
+except ImportError:
+    from PySide import QtCore, QtGui
+    QtWidgets = QtGui
```

## 配套配置

除了源码兼容修复，还需要确保 MCP 自动启动开关已经启用。

配置文件：

- `~/.FreeCAD/freecad_mcp_settings.json`

推荐内容：

```json
{
  "remote_enabled": false,
  "allowed_ips": "127.0.0.1",
  "auto_start_rpc": true
}
```

说明：

- `remote_enabled: false`
  表示仅监听本机 `localhost`
- `allowed_ips: "127.0.0.1"`
  表示仅允许本机访问
- `auto_start_rpc: true`
  表示 FreeCAD 启动后自动拉起 RPC 服务

## 应用步骤

1. 修改 `rpc_server.py`
2. 写入或更新 `~/.FreeCAD/freecad_mcp_settings.json`
3. 重启 FreeCAD

示例命令：

```bash
su - lthpc -c '/usr/local/bin/start-remote-cad-desktop freecad stop; sleep 1; /usr/local/bin/start-freecad-remote'
```

## 验证步骤

### 1. 检查端口

```bash
curl -sS http://localhost:9876
```

如果只是普通 HTTP GET，XML-RPC 服务通常不会返回业务内容；更稳妥的是做 XML-RPC `ping()`。

### 2. 检查 XML-RPC

```bash
python3 - <<'PY'
import socket, xmlrpc.client
socket.setdefaulttimeout(2)
server = xmlrpc.client.ServerProxy("http://localhost:9876", allow_none=True)
print(server.ping())
PY
```

预期输出：

```text
True
```

### 3. 检查 CLI

```bash
freecad-list-docs
freecad-exec-code "import FreeCAD; print('rpc-ok')"
```

## 结果

应用以上修复后，当前环境已经验证：

- `FreeCADMCP` 自动启动恢复正常
- `localhost:9876` 成功监听
- XML-RPC `ping()` 返回 `True`
- `freecad-*` CLI 可以重新访问 FreeCAD

## 建议

如果后续更新或重装 `FreeCADMCP`，优先重新检查这两项：

1. `rpc_server.py` 中的 `PySide` 导入是否仍兼容 FreeCAD 0.19
2. `~/.FreeCAD/freecad_mcp_settings.json` 中的 `auto_start_rpc` 是否仍为 `true`
