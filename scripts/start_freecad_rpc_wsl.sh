#!/usr/bin/env bash
set -euo pipefail

source /root/miniconda3/etc/profile.d/conda.sh
conda activate freecad

export HOME=/root
export DISPLAY=:99

mkdir -p /root/.local/share/FreeCAD

if ! pgrep -f "Xvfb :99" >/dev/null; then
  nohup Xvfb :99 -screen 0 1600x1200x24 >/tmp/xvfb.log 2>&1 &
  sleep 2
fi

nohup freecad >/tmp/freecad-rpc.log 2>&1 &
