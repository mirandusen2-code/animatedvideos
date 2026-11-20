"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

from PIL import Image

import post
import timeline as T

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
f_spray = int((T.T_SPRAY2 + 0.35) * T.FPS)
f_xray = int((T.T_FIRE + 0.05) * T.FPS)
f_tongue = int((T.T_TONGUE - 0.02) * T.FPS)
for name, f, lines, colors, y in [
    ("thumb_spray", f_spray, [["212°F"], ["BUTT", "SPRAY"]], {0: post.AMBER, 2: post.ICE}, 1250),
    ("thumb_xray", f_xray, [["IT", "EXPLODES"], ["INSIDE", "THE", "TOAD"]], {1: post.AMBER, 4: post.ICE}, 1250),
    ("thumb_tongue", f_tongue, [["BAD", "IDEA,"], ["TOAD"]], {1: post.AMBER}, 1250),
]:
    t = f / T.FPS
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, y, 118, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name, f)
