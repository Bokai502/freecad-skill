#!/usr/bin/env bash
set -euo pipefail

pkill -x freecad || true
pkill -x Xvfb || true

source /root/miniconda3/etc/profile.d/conda.sh
conda activate freecad

export HOME=/root
export QT_QPA_PLATFORM=xcb
mkdir -p /root/.local/share/FreeCAD
rm -f /tmp/freecad-rpc.log /tmp/freecad-launch.log /tmp/xvfb.log

# Keep FreeCAD detached from the launching shell and always emit a persistent log.
setsid xvfb-run -a -s "-screen 0 1600x1200x24" \
  freecad --write-log --log-file /tmp/freecad-rpc.log \
  >/tmp/freecad-launch.log 2>&1 < /dev/null &

for _ in $(seq 1 30); do
  if ss -ltn 2>/dev/null | grep -q ':9875 '; then
    break
  fi
  sleep 1
done

pgrep -a Xvfb || true
pgrep -a freecad || true
echo "---PORT---"
ss -ltn 2>/dev/null | grep ':9875 ' || true
echo "---LAUNCH---"
sed -n '1,200p' /tmp/freecad-launch.log || true
echo "---FREECAD---"
sed -n '1,200p' /tmp/freecad-rpc.log || true
