"""QA: contact sheets of EVERY frame of a video (100 per sheet, 10x10), with frame number, time, shot
boundaries and the phone UI zones, so every single frame can be reviewed by eye.

Usage: python3 qa_sheets.py <video.mp4> <out_dir> [--cuts f1,f2,...]
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

video, out = sys.argv[1], sys.argv[2]
cuts = set()
if "--cuts" in sys.argv:
    cuts = {int(v) for v in sys.argv[sys.argv.index("--cuts") + 1].split(",")}
os.makedirs(out, exist_ok=True)
W, H = 162, 288
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                      "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
k = W / 1080
n_sheets = (len(frames) + 99) // 100
for s in range(n_sheets):
    sheet = Image.new("RGB", (10 * (W + 4), 10 * (H + 18)), "white")
    d = ImageDraw.Draw(sheet)
    for i in range(100):
        f = s * 100 + i
        if f >= len(frames):
            break
        im = Image.fromarray(frames[f])
        dd = ImageDraw.Draw(im, "RGBA")
        dd.rectangle([0, 0, W, 260 * k], fill=(255, 0, 0, 40))                 # top UI
        dd.rectangle([880 * k, 1050 * k, W, 1760 * k], fill=(255, 0, 0, 40))   # buttons
        dd.rectangle([0, 1580 * k, W, H], fill=(255, 0, 0, 40))                # title/channel
        X, Y = (i % 10) * (W + 4), (i // 10) * (H + 18)
        sheet.paste(im, (X, Y + 16))
        col = (200, 0, 0) if f in cuts else (0, 0, 0)
        d.text((X + 2, Y + 2), f"{f} {f / 30:.2f}s" + ("  CUT" if f in cuts else ""), fill=col)
    sheet.save(os.path.join(out, f"sheet_{s:02d}.png"))
print(f"{len(frames)} frames -> {n_sheets} sheets in {out}")
