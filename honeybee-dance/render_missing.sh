#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${FRAME_DIR:?Set FRAME_DIR to a folder outside the checkout}"
python - "$1" "$2" <<'PY'
import os,sys
from pathlib import Path
from PIL import Image
from art import frame
from timeline import NFRAMES
folder=Path(os.environ['FRAME_DIR']);folder.mkdir(parents=True,exist_ok=True)
for i in range(int(sys.argv[1]),min(int(sys.argv[2]),NFRAMES)):
    p=folder/f'{i:05}.png'
    if p.exists():
        try:
            with Image.open(p) as im:
                im.load()
                if im.size!=(1080,1920):raise ValueError(im.size)
            continue
        except (OSError,ValueError):p.unlink()
    tmp=p.with_suffix('.part.png')
    frame(i).save(tmp,compress_level=2)
    tmp.replace(p)
PY
