"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
GREEN = (120, 235, 170)
f_hero = int(0.75 * T.FPS)
f_polyp = int((T.SHOTS[4][1] - 0.15) * T.FPS)
f_life = int((T.T_AGAIN[2] + 0.5) * T.FPS)
for name, f, lines, colors, y in [
    ("thumb_forever", f_hero, [["IT", "NEVER"], ["DIES"]], {1: post.AMBER, 2: post.AMBER}, 1250),
    ("thumb_baby", f_polyp, [["IT", "TURNS"], ["BACK", "INTO", "A"], ["BABY"]], {4: post.ICE}, 1250),
    ("thumb_life", f_life, [["LIFE", "#4"]], {1: GREEN}, 1250),
]:
    t = f / T.FPS
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, y, 124, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
