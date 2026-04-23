#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_RUNTIME_CONFIG="${SCRIPT_DIR}/config/freecad_runtime.conf"
RUNTIME_CONFIG_PATH="${FREECAD_RUNTIME_CONFIG:-${DEFAULT_RUNTIME_CONFIG}}"

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
      FREECAD_RPC_HOST|FREECAD_RPC_PORT|FREECAD_RUNTIME_DATA_DIR)
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
FREECAD_BIN="${FREECAD_BIN:-/home/xie/.local/bin/freecad}"
FREECAD_APP_REGEX="${FREECAD_APP_REGEX:-/home/xie/.local/bin/freecad|/tmp/.mount_freeca.*/usr/bin/freecad|/usr/bin/freecad}"

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

list_x_clients() {
  DISPLAY="${DISPLAY_NUM}" xlsclients -l 2>/dev/null || true
}

has_freecad_x_client() {
  list_x_clients | grep -qi "freecad"
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
  echo "runtime_data_dir=${FREECAD_RUNTIME_DATA_DIR:-/tmp/freecad_data}"
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
  restart)
    stop_session
    sleep 1
    ;;
  status)
    status_session
    exit 0
    ;;
  start)
    ;;
  *)
    echo "用法: $0 [start|stop|restart|status]"
    echo "可选环境变量: DISPLAY_NUM=:11 VNC_PORT=5911 NOVNC_PORT=7080 FREECAD_BIN=/home/xie/.local/bin/freecad FREECAD_RUNTIME_CONFIG=${DEFAULT_RUNTIME_CONFIG}"
    exit 1
    ;;
esac

if [[ ! -x "${FREECAD_BIN}" ]]; then
  echo "未找到 FreeCAD 可执行文件：${FREECAD_BIN}"
  exit 1
fi

if ! pgrep -f "Xvfb ${DISPLAY_NUM}" >/dev/null 2>&1; then
  nohup Xvfb "${DISPLAY_NUM}" -screen 0 1920x1080x24 >"${XVFB_LOG}" 2>&1 &
  sleep 1
fi

if ! pgrep -f "env DISPLAY=${DISPLAY_NUM} openbox|DISPLAY=${DISPLAY_NUM} .*openbox" >/dev/null 2>&1; then
  nohup env DISPLAY="${DISPLAY_NUM}" openbox >"${OPENBOX_LOG}" 2>&1 &
  sleep 1
fi

if ! pgrep -f "x11vnc .* -display ${DISPLAY_NUM} .* -rfbport ${VNC_PORT}" >/dev/null 2>&1; then
  nohup x11vnc -display "${DISPLAY_NUM}" -localhost -forever -shared -nopw -rfbport "${VNC_PORT}" >"${X11VNC_LOG}" 2>&1 &
  sleep 1
fi

if ! is_port_listening "${NOVNC_PORT}"; then
  nohup "${NOVNC_PROXY}" --vnc localhost:"${VNC_PORT}" --listen "${NOVNC_PORT}" >"${NOVNC_LOG}" 2>&1 &
  sleep 1
fi

if ! has_freecad_x_client; then
  rm -f "${FREECAD_LOG}" "${FREECAD_LOG}.launch"
  nohup env DISPLAY="${DISPLAY_NUM}" \
    LIBGL_ALWAYS_SOFTWARE=1 \
    MESA_GL_VERSION_OVERRIDE=3.3 \
    FREECAD_RUNTIME_CONFIG="${RUNTIME_CONFIG_PATH}" \
    FREECAD_RPC_HOST="${FREECAD_RPC_HOST:-localhost}" \
    FREECAD_RPC_PORT="${FREECAD_RPC_PORT:-9876}" \
    FREECAD_RUNTIME_DATA_DIR="${FREECAD_RUNTIME_DATA_DIR:-/tmp/freecad_data}" \
    "${FREECAD_BIN}" --write-log --log-file "${FREECAD_LOG}" >"${FREECAD_LOG}.launch" 2>&1 &
  for _ in $(seq 1 20); do
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
