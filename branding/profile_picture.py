"""Profile picture for the 'MindBlown 3D' channel: an exploding cartoon brain.

Usage: python3 profile_picture.py [out.png]   -> 800x800 PNG (YouTube's recommended size)
"""
import math
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

S = 2048                      # draw big, downscale for smooth edges
OUT = 800
C = S / 2


def radial_bg():
    y, x = np.mgrid[0:S, 0:S]
    r = np.sqrt((x - C) ** 2 + (y - C * 0.95) ** 2) / (S * 0.72)
    inner = np.array([150, 40, 255], float)      # violet
    outer = np.array([20, 8, 60], float)         # deep indigo
    t = np.clip(r, 0, 1)[..., None]
    return Image.fromarray((inner * (1 - t) + outer * t).astype(np.uint8), "RGB").convert("RGBA")


def star(cx, cy, r_out, r_in, n, rot=0.0, jitter=0.0, seed=1):
    rnd = random.Random(seed)
    pts = []
    for i in range(n * 2):
        a = rot + math.pi * i / n
        r = (r_out if i % 2 == 0 else r_in) * (1 + rnd.uniform(-jitter, jitter))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "mindblown3d_profile.png"
    img = radial_bg()

    # explosion burst behind the brain (glow + 3 layered stars)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([C - 760, C - 900, C + 760, C + 560], fill=(255, 170, 40, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(img)
    bx, by = C, C - 250
    d.polygon(star(bx, by, 800, 430, 14, rot=0.1, jitter=0.12, seed=3), fill=(255, 92, 40))
    d.polygon(star(bx, by, 640, 360, 12, rot=0.35, jitter=0.12, seed=5), fill=(255, 170, 30))
    d.polygon(star(bx, by, 470, 270, 10, rot=0.2, jitter=0.1, seed=7), fill=(255, 236, 120))

    # brain: cloud of overlapping circles, outlined
    lobes = [(-330, 60, 250), (-150, -110, 270), (120, -130, 270), (330, 40, 250),
             (-230, 230, 230), (40, 200, 260), (260, 230, 220), (-20, -10, 300)]
    cy = C + 170
    outline = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    od = ImageDraw.Draw(outline)
    for x, y, r in lobes:
        r2 = r + 34
        od.ellipse([C + x - r2, cy + y - r2, C + x + r2, cy + y + r2], fill=(60, 10, 50, 255))
    img.alpha_composite(outline)
    d = ImageDraw.Draw(img)
    for x, y, r in lobes:
        d.ellipse([C + x - r, cy + y - r, C + x + r, cy + y + r], fill=(255, 140, 190))
    # soft highlight
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse([C - 420, cy - 360, C + 60, cy - 60], fill=(255, 220, 235, 55))
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(50)))
    d = ImageDraw.Draw(img)
    # center split + folds (gyri)
    w = 30
    fold = (190, 60, 120)
    d.line([(C, cy - 330), (C - 30, cy - 120), (C + 20, cy + 60), (C - 10, cy + 300)], fill=fold, width=w, joint="curve")
    for x, y, r, a0, a1 in [(-300, 40, 120, 200, 340), (-150, -120, 110, 20, 160), (-250, 230, 110, 180, 330),
                            (300, 40, 120, 200, 340), (150, -120, 110, 20, 160), (240, 230, 110, 180, 330),
                            (-120, 120, 90, 250, 400), (120, 120, 90, 140, 290)]:
        d.arc([C + x - r, cy + y - r, C + x + r, cy + y + r], a0, a1, fill=fold, width=w)

    # sparkles
    for (x, y, r) in [(-700, -520, 90), (690, -430, 70), (-620, 300, 55), (650, 420, 80), (40, -820, 60)]:
        d.polygon(star(C + x, C + y, r, r * 0.28, 4, rot=-math.pi / 2), fill=(255, 255, 255))

    img.convert("RGB").resize((OUT, OUT), Image.LANCZOS).save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
