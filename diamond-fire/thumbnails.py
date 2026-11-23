"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_burning", 12, [["THIS", "DIAMOND"], ["IS", "BURNING"]], {3: post.AMBER}, 520),
    ("thumb_thin_air", int((T.T_BREATHE) * T.FPS), [["INTO", "THIN"], ["AIR"]], {2: post.AMBER}, 520),
    ("thumb_forever", int((T.SHOTS[5][0] + 1.2) * T.FPS), [["NOT", "FOREVER"]], {1: post.AMBER}, 520),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
