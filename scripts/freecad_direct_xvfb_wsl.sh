#!/usr/bin/env bash
set -euo pipefail

source /root/miniconda3/etc/profile.d/conda.sh
conda activate freecad

export HOME=/root
export QT_QPA_PLATFORM=xcb

exec xvfb-run -a -s "-screen 0 1600x1200x24" freecad --write-log --log-file /tmp/freecad-direct.log
