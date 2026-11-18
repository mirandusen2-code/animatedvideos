#!/usr/bin/env bash
# Render all frames in batches of 50, each in a fresh Blender process (skips frames that already exist).
# Usage: ./render_all.sh <frames_dir> [res] [samples]
set -e
OUT=$1; RES=${2:-576x1024}; SPP=${3:-4}
cd "$(dirname "$0")"
for start in $(seq 0 50 1049); do
  end=$((start + 49)); [ $end -gt 1049 ] && end=1049
  python3 blender_scene.py "$OUT" --frames "$(seq -s, $start $end)" --res "$RES" --samples "$SPP" > /dev/null 2>&1
  echo "batch $start-$end done"
done
echo "ALL DONE"
