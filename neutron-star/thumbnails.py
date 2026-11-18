"""Three thumbnail candidates (1080x1920) from the most striking frames, with a short title in the safe zone.
Usage: python3 thumbnails.py <frames_dir> <out_dir>"""
import os
import sys

import post

frames, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
for name, f, lines, colors in [
    ("thumb_scale", 40, [["1", "SUGAR", "CUBE"], [">", "8", "BILLION"], ["PEOPLE"]], {0: post.AMBER, 4: post.AMBER, 5: post.AMBER}),
    ("thumb_glowing_cube", 870, [["1", "BILLION"], ["TONS"]], {0: post.AMBER, 1: post.AMBER}),
    ("thumb_pulsar", 700, [["716", "SPINS"], ["PER", "SECOND"]], {0: post.ICE}),
]:
    t = f / post.T.FPS
    from PIL import Image
    img = post.finish(Image.open(os.path.join(frames, f"f_{f:04d}.png")).convert("RGB"), t)
    post.text_block(img, lines, post.CX, 520, 118, colors=colors)
    img.convert("RGB").save(os.path.join(out, f"{name}.png"))
    print("saved", name)
