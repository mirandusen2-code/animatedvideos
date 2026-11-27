"""Three thumbnail candidates (1080x1920). Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_square_windows", 0, [["SQUARE"], ["WINDOWS"]], {0: post.HOT}, 1340),
    ("thumb_why_round", 352, [["WHY ARE"], ["WINDOWS"], ["ROUND?"]], {2: post.HOT}, 560),
    ("thumb_1954", 120, [["1954:"], ["JETS RIPPED"], ["APART"]], {0: post.HOT}, 1340),
]:
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), f / T.FPS)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
