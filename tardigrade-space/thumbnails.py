"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors, y in [
    ("thumb_space", 95, [["10", "DAYS", "IN"], ["OPEN", "SPACE"]], {0: post.AMBER, 1: post.AMBER, 4: post.ICE}, 1250),
    ("thumb_moon", 720, [["STILL", "ALIVE"], ["ON", "THE", "MOON?"]], {1: post.AMBER, 4: post.AMBER}, 560),
    ("thumb_ruler", 200, [["0.5", "MM"], ["SPACE", "SURVIVOR"]], {0: post.AMBER, 1: post.AMBER, 2: post.ICE}, 1420),
]:
    t = f / post.T.FPS
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, y, 118, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name)
