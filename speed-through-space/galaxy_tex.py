"""Procedural face-on Milky Way texture (barred spiral): warm bulge and bar, four logarithmic arms with blue
stars and pink star-forming clumps, dark dust lanes on the inner edge of the arms, a soft disk and star speckle.
Writes an RGBA PNG (alpha = brightness, so it can be layered as an emissive sheet in Blender).

Usage: python3 galaxy_tex.py <out.png> [size]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

N = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
rng = np.random.default_rng(42)
y, x = (np.mgrid[0:N, 0:N] + 0.5) / N * 2 - 1          # -1..1
r = np.hypot(x, y) + 1e-6
th = np.arctan2(y, x)
PITCH = np.radians(21.0)
BAR_A = np.radians(25.0)


def arm_dist(theta0, w):
    """Angular distance to a log-spiral arm starting at theta0, converted to a lateral distance."""
    phase = theta0 + np.log(r / 0.2) / np.tan(PITCH)
    d = np.angle(np.exp(1j * (th + WARP - phase)))
    return np.abs(d) * r, d


def noise(scale, octaves=5, seed=0):
    g = np.zeros((N, N))
    rr = np.random.default_rng(seed)
    amp = 1.0
    tot = 0.0
    for o in range(octaves):
        s = max(4, int(scale * 2 ** o))
        a = rr.random((s, s))
        im = Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)
        g += amp * np.asarray(im) / 255.0
        tot += amp
        amp *= 0.5
    return g / tot


n1 = noise(6, seed=1)
n2 = noise(24, seed=2)
n3 = noise(10, seed=4)
WARP = (n3 - 0.5) * 0.9 * np.clip(r / 0.5, 0, 1)        # arms wobble instead of being perfect spirals
arms = np.zeros((N, N))
dust = np.zeros((N, N))
for k, (t0, strength, width) in enumerate([(0.0, 1.0, 0.12), (np.pi, 1.0, 0.12),
                                           (np.pi / 2, 0.6, 0.09), (3 * np.pi / 2, 0.6, 0.09)]):
    dd, signed = arm_dist(t0 + BAR_A, width)
    w = width * (0.6 + 0.8 * r)
    arms += strength * np.exp(-(dd / w) ** 2)
    # dust lane just on the inner (trailing) side of each major arm
    lane = np.exp(-(((signed * r) + 0.45 * w) / (0.45 * w)) ** 2) * strength
    dust += lane
fade_in = np.clip((r - 0.10) / 0.12, 0, 1)
fade_out = np.exp(-((r / 0.82) ** 6))
arms *= fade_in * fade_out * np.clip(0.15 + 1.5 * (n2 - 0.3), 0, 1.6) * (0.6 + 0.6 * n1)
dust *= fade_in * fade_out * (0.5 + n1)

# bar + bulge
c, s = np.cos(BAR_A), np.sin(BAR_A)
bx, by = x * c + y * s, -x * s + y * c
bar = np.exp(-((bx / 0.20) ** 2 + (by / 0.06) ** 2))
bulge = np.exp(-(r / 0.07) ** 2) * 1.6 + np.exp(-(r / 0.16) ** 2) * 0.5
disk = np.exp(-r / 0.30) * 0.55 * fade_out * (0.75 + 0.5 * n2)

lum = disk + arms * 0.9 + bar * 0.9 + bulge
col = np.zeros((N, N, 3))
warm = np.array([1.0, 0.80, 0.55])
blue = np.array([0.62, 0.78, 1.0])
col += (bulge + bar * 0.9)[..., None] * warm
col += disk[..., None] * np.array([0.9, 0.82, 0.75])
col += (arms * 1.35)[..., None] * blue
# star-forming clumps (pink) scattered along the arms
clumps = np.zeros((N, N))
pts = rng.random((6000, 2)) * 2 - 1
for px, py in pts:
    i, j = int((py + 1) / 2 * N), int((px + 1) / 2 * N)
    if 0 <= i < N and 0 <= j < N and arms[i, j] > 0.35:
        clumps[i, j] = rng.uniform(0.6, 1.0)
clumps = np.asarray(Image.fromarray((clumps * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(N / 1400))).astype(float) / 255 * 30
col += clumps[..., None] * np.array([1.0, 0.45, 0.6])
# dust darkens
col *= (1 - np.clip(dust * 0.45, 0, 0.55))[..., None]
# star speckle, denser where the galaxy is bright
star = (rng.random((N, N)) < (0.001 + 0.03 * np.clip(lum, 0, 1))) * rng.uniform(0.4, 1.0, (N, N))
star = np.asarray(Image.fromarray((star * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(float) / 255 * 3
col += star[..., None] * np.array([1.0, 0.97, 0.92])
col = 1 - np.exp(-col * 1.6)                       # soft tone map
alpha = np.clip(col.max(axis=-1) * 1.4, 0, 1) * np.clip((1 - r) / 0.12, 0, 1)
out = np.dstack([np.clip(col, 0, 1), alpha])
Image.fromarray((out * 255).astype(np.uint8), "RGBA").save(sys.argv[1])
Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).resize((800, 800)).save(sys.argv[1].replace(".png", "_prev.png"))
