#!/usr/bin/env bash
set -euo pipefail

pkill -x freecad || true
pkill -x Xvfb || true

source /root/miniconda3/etc/profile.d/conda.sh
conda activate freecad

export HOME=/root
mkdir -p /root/.local/share/FreeCAD
rm -f /tmp/freecad-rpc.log /tmp/freecad-launch.log

if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
  echo "WSLg display variables are not available. Start this from a WSLg-enabled session." >&2
  exit 1
fi

# Prefer XWayland in WSLg because this FreeCAD build does not ship the Wayland Qt plugin.
if [[ -n "${DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
else
  unset QT_QPA_PLATFORM || true
fi

setsid freecad --write-log --log-file /tmp/freecad-rpc.log \
  >/tmp/freecad-launch.log 2>&1 < /dev/null &

for _ in $(seq 1 30); do
  if ss -ltn 2>/dev/null | grep -q ':9875 '; then
    break
  fi
  sleep 1
done

pgrep -a freecad || true
echo "---DISPLAY---"
echo "DISPLAY=${DISPLAY:-}"
echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-}"
echo "QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-auto}"
echo "---PORT---"
ss -ltn 2>/dev/null | grep ':9875 ' || true
echo "---LAUNCH---"
sed -n '1,120p' /tmp/freecad-launch.log || true
echo "---FREECAD---"
sed -n '1,120p' /tmp/freecad-rpc.log || true
