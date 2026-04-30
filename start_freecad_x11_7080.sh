#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEGACY_RUNTIME_CONFIG="${SCRIPT_DIR}/config/freecad_runtime.conf"

find_runtime_config() {
  if [[ -n "${FREECAD_RUNTIME_CONFIG:-}" ]]; then
    printf '%s\n' "${FREECAD_RUNTIME_CONFIG}"
    return 0
  fi

  local user_config_home="${XDG_CONFIG_HOME:-${HOME}/.config}"
  local candidate
  for candidate in \
    "${PWD}/.freecad/freecad_runtime.conf" \
    "${PWD}/freecad_runtime.conf" \
    "${user_config_home}/freecad-cli-tools/runtime.conf" \
    "${LEGACY_RUNTIME_CONFIG}"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done
}

RUNTIME_CONFIG_PATH="$(find_runtime_config || true)"

load_runtime_config() {
  local config_path="$1"
  if [[ ! -f "${config_path}" ]]; then
    return 0
  fi

  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    local line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    if [[ -z "${line}" || "${line}" == \#* || "${line}" != *=* ]]; then
      continue
    fi
    local key="${line%%=*}"
    local value="${line#*=}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    case "${key}" in
      FREECAD_RPC_HOST|FREECAD_RPC_PORT|FREECAD_WORKSPACE_DIR|FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB|FREECAD_RPC_PROBE_TIMEOUT_SECONDS|FREECAD_STARTUP_WAIT_SECONDS)
        if [[ -z "${!key:-}" ]]; then
          printf -v "${key}" '%s' "${value}"
          export "${key}"
        fi
        ;;
    esac
  done < "${config_path}"
}

load_runtime_config "${RUNTIME_CONFIG_PATH}"

ACTION="${1:-start}"

DISPLAY_NUM="${DISPLAY_NUM:-:11}"
VNC_PORT="${VNC_PORT:-5911}"
NOVNC_PORT="${NOVNC_PORT:-7080}"
LOG_DIR="${LOG_DIR:-/tmp/freecad-remote-${NOVNC_PORT}}"
NOVNC_LOG="${LOG_DIR}/novnc.log"
XVFB_LOG="${LOG_DIR}/xvfb.log"
OPENBOX_LOG="${LOG_DIR}/openbox.log"
X11VNC_LOG="${LOG_DIR}/x11vnc.log"
FREECAD_LOG="${LOG_DIR}/freecad.log"
RESOURCE_SNAPSHOT_LOG="${LOG_DIR}/resource_snapshot.log"
FREECAD_BIN="${FREECAD_BIN:-/home/xie/.local/bin/freecad}"
FREECAD_APP_REGEX="${FREECAD_APP_REGEX:-/home/xie/.local/bin/freecad|/tmp/.mount_freeca.*/usr/bin/freecad|/usr/bin/freecad}"
FREECAD_STARTUP_WAIT_SECONDS="${FREECAD_STARTUP_WAIT_SECONDS:-20}"
FREECAD_RPC_PROBE_TIMEOUT_SECONDS="${FREECAD_RPC_PROBE_TIMEOUT_SECONDS:-15}"
FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB="${FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB:-100}"

mkdir -p "${LOG_DIR}"

NOVNC_PROXY=""
for candidate in /usr/share/novnc/utils/novnc_proxy /usr/share/novnc/utils/launch.sh; do
  if [[ -x "${candidate}" ]]; then
    NOVNC_PROXY="${candidate}"
    break
  fi
done

if [[ -z "${NOVNC_PROXY}" ]]; then
  echo "未找到 noVNC 启动程序。"
  exit 1
fi

is_port_listening() {
  ss -ltn "( sport = :$1 )" 2>/dev/null | grep -q ":$1"
}

start_detached() {
  local log_file="$1"
  shift

  if command -v setsid >/dev/null 2>&1; then
    nohup setsid "$@" >"${log_file}" 2>&1 < /dev/null &
  else
    nohup "$@" >"${log_file}" 2>&1 < /dev/null &
  fi
}

write_resource_snapshot() {
  {
    echo "timestamp=$(date --iso-8601=seconds)"
    echo "hostname=$(hostname)"
    echo "nproc=$(nproc 2>/dev/null || echo unknown)"
    echo "freecad_rpc=${FREECAD_RPC_HOST:-localhost}:${FREECAD_RPC_PORT:-9876}"
    echo "workspace_dir=${FREECAD_WORKSPACE_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
    echo "component_info_max_step_size_mb=${FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB}"
    echo
    echo "[free -h]"
    free -h || true
    echo
    echo "[df -h /tmp]"
    df -h /tmp || true
    echo
    echo "[ulimit -a]"
    ulimit -a || true
  } >> "${RESOURCE_SNAPSHOT_LOG}"
}

list_x_clients() {
  DISPLAY="${DISPLAY_NUM}" xlsclients -l 2>/dev/null || true
}

list_x_windows() {
  DISPLAY="${DISPLAY_NUM}" xprop -root _NET_CLIENT_LIST 2>/dev/null || true
}

has_freecad_x_client() {
  if list_x_clients | grep -qi "freecad"; then
    return 0
  fi

  local window_ids
  window_ids="$(list_x_windows | grep -o '0x[0-9a-fA-F]\+')"
  if [[ -z "${window_ids}" ]]; then
    return 1
  fi

  local window_id
  for window_id in ${window_ids}; do
    if DISPLAY="${DISPLAY_NUM}" xprop -id "${window_id}" WM_CLASS WM_NAME 2>/dev/null | grep -qi "freecad"; then
      return 0
    fi
  done

  return 1
}

probe_rpc() {
  local host="${FREECAD_RPC_HOST:-localhost}"
  local port="${FREECAD_RPC_PORT:-9876}"
  local timeout="${FREECAD_RPC_PROBE_TIMEOUT_SECONDS}"
  python3 - "$host" "$port" "$timeout" <<'PY'
import json
import socket
import sys
import xmlrpc.client

host = sys.argv[1]
port = int(sys.argv[2])
timeout = float(sys.argv[3])
socket.setdefaulttimeout(timeout)
proxy = xmlrpc.client.ServerProxy(f"http://{host}:{port}/", allow_none=True)
result = proxy.execute_code(
    "import json, FreeCAD; "
    "print(json.dumps({'success': True, 'active_document': FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else None}))"
)
print(result)
PY
}

stop_session() {
  pkill -f "${FREECAD_APP_REGEX}" >/dev/null 2>&1 || true
  pkill -f "${NOVNC_PROXY}.*${NOVNC_PORT}" >/dev/null 2>&1 || true
  pkill -f "websockify --web .* ${NOVNC_PORT} localhost:${VNC_PORT}" >/dev/null 2>&1 || true
  pkill -f "x11vnc .* -display ${DISPLAY_NUM} .* -rfbport ${VNC_PORT}" >/dev/null 2>&1 || true
  pkill -f "env DISPLAY=${DISPLAY_NUM} openbox|DISPLAY=${DISPLAY_NUM} .*openbox" >/dev/null 2>&1 || true
  pkill -f "Xvfb ${DISPLAY_NUM} " >/dev/null 2>&1 || true
}

status_session() {
  echo "DISPLAY=${DISPLAY_NUM} VNC=${VNC_PORT} noVNC=${NOVNC_PORT}"
  echo "freecad_bin=${FREECAD_BIN}"
  echo "runtime_config=${RUNTIME_CONFIG_PATH}"
  echo "freecad_rpc=${FREECAD_RPC_HOST:-localhost}:${FREECAD_RPC_PORT:-9876}"
  echo "workspace_dir=${FREECAD_WORKSPACE_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
  echo "component_info_max_step_size_mb=${FREECAD_COMPONENT_INFO_MAX_STEP_SIZE_MB}"
  if is_port_listening "${VNC_PORT}"; then
    echo "backend: localhost:${VNC_PORT} is listening"
  else
    echo "backend: localhost:${VNC_PORT} is not listening"
  fi
  if is_port_listening "${NOVNC_PORT}"; then
    echo "novnc: localhost:${NOVNC_PORT} is listening"
  else
    echo "novnc: localhost:${NOVNC_PORT} is not listening"
  fi
  if has_freecad_x_client; then
    echo "freecad_gui: attached to X display ${DISPLAY_NUM}"
  else
    echo "freecad_gui: not attached to X display ${DISPLAY_NUM}"
  fi
}

case "${ACTION}" in
  stop)
    stop_session
    echo "FreeCAD 7080 远程桌面已停止。"
    exit 0
    ;;
  fresh-start|prepare-heavy)
    stop_session
    sleep 1
    ;;
  restart)
    stop_session
    sleep 1
    ;;
  status)
    status_session
    exit 0
    ;;
  probe)
    probe_rpc
    exit 0
    ;;
  start)
    ;;
  *)
    echo "用法: $0 [start|stop|restart|fresh-start|prepare-heavy|status|probe]"
    echo "可选环境变量: DISPLAY_NUM=:11 VNC_PORT=5911 NOVNC_PORT=7080 FREECAD_BIN=/home/xie/.local/bin/freecad FREECAD_RUNTIME_CONFIG=${LEGACY_RUNTIME_CONFIG}"
    exit 1
    ;;
esac

if [[ ! -x "${FREECAD_BIN}" ]]; then
  echo "未找到 FreeCAD 可执行文件：${FREECAD_BIN}"
  exit 1
fi

if ! pgrep -f "Xvfb ${DISPLAY_NUM}" >/dev/null 2>&1; then
  start_detached "${XVFB_LOG}" Xvfb "${DISPLAY_NUM}" -screen 0 1920x1080x24
  sleep 1
fi

if ! pgrep -f "env DISPLAY=${DISPLAY_NUM} openbox|DISPLAY=${DISPLAY_NUM} .*openbox" >/dev/null 2>&1; then
  start_detached "${OPENBOX_LOG}" env DISPLAY="${DISPLAY_NUM}" openbox
  sleep 1
fi

if ! pgrep -f "x11vnc .* -display ${DISPLAY_NUM} .* -rfbport ${VNC_PORT}" >/dev/null 2>&1; then
  start_detached "${X11VNC_LOG}" x11vnc -display "${DISPLAY_NUM}" -localhost -forever -shared -nopw -rfbport "${VNC_PORT}"
  sleep 1
fi

if ! is_port_listening "${NOVNC_PORT}"; then
  start_detached "${NOVNC_LOG}" "${NOVNC_PROXY}" --vnc localhost:"${VNC_PORT}" --listen "${NOVNC_PORT}"
  sleep 1
fi

if ! has_freecad_x_client; then
  rm -f "${FREECAD_LOG}" "${FREECAD_LOG}.launch"
  write_resource_snapshot
  start_detached "${FREECAD_LOG}.launch" env DISPLAY="${DISPLAY_NUM}" \
    LIBGL_ALWAYS_SOFTWARE=1 \
    MESA_GL_VERSION_OVERRIDE=3.3 \
    FREECAD_RUNTIME_CONFIG="${RUNTIME_CONFIG_PATH}" \
    FREECAD_RPC_HOST="${FREECAD_RPC_HOST:-localhost}" \
    FREECAD_RPC_PORT="${FREECAD_RPC_PORT:-9876}" \
    FREECAD_WORKSPACE_DIR="${FREECAD_WORKSPACE_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}" \
    "${FREECAD_BIN}" --write-log --log-file "${FREECAD_LOG}"
  for _ in $(seq 1 "${FREECAD_STARTUP_WAIT_SECONDS}"); do
    sleep 1
    if has_freecad_x_client; then
      break
    fi
  done
fi

if ! has_freecad_x_client; then
  echo "FreeCAD GUI 未附着到 ${DISPLAY_NUM}，请检查："
  echo "  ${FREECAD_LOG}"
  echo "  ${FREECAD_LOG}.launch"
  exit 1
fi

echo "FreeCAD X11 会话已桥接到 noVNC。"
echo "浏览器访问：http://10.110.10.11:${NOVNC_PORT}/vnc.html?autoconnect=true&resize=scale&path=websockify"
echo "日志目录：${LOG_DIR}"
