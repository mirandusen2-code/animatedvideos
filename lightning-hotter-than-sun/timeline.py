"""Shot timeline for "Lightning Is 5x Hotter Than the Sun", derived from the real narration timing (vo/timing.json).

Sets (far apart in one Blender scene):
  storm: night field with a lone tree; the bolt strikes it at t = 0 (the loop seam), a stepped leader comes
         down in the last shot so the strike at frame 0 is the payoff of the loop.
  macro: close-ups of a glowing channel segment (heat, shock wave, ruler) at MACRO.
  sun:   the Sun's surface at SUNSET_.
  earth: Earth's night side with lightning flashes, at EARTHSET.
"""
import json
import math
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
NFRAMES = round((L["loop"][1] + 0.05) * FPS)
DUR = NFRAMES / FPS

MACRO = (500.0, 0.0, 0.0)
SUNSET_ = (1000.0, 0.0, 0.0)
EARTHSET = (2000.0, 0.0, 0.0)


def W(line, word, n=0):
    a, b = L[line]
    k = 0
    for s, e, w, *_ in WORDS:
        if a - 0.01 <= s <= b + 0.01 and word.lower() in re.sub(r"[^a-z0-9]", "", w.lower()):
            if k == n:
                return s, e
            k += 1
    raise KeyError((line, word, n))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(a, b):
    return tuple(p + q for p, q in zip(a, b))


T_HOTTER = W("hook", "hotter")[0]
T_SUNW = W("hook", "sun")[0]
T_50 = W("heat", "50000")[0]
T_SUN2 = W("sun", "sun")[0]
T_10 = W("sun", "10000")[0]
T_FAST = W("boom", "fast")[0]
T_EXPL = W("boom", "explodes")[0]
T_THUNDER = W("boom", "thunder")[0]
T_INCH = W("inch", "inch")[0]
T_44 = W("count", "44")[0]
T_EARTH = W("count", "earth")[0]
T_SEE = W("loop", "see")[0]

# ---------------------------------------------------------------- strikes in the storm (relative to the loop clock)
# (time, which bolt, peak brightness). Bolt 0 hits the tree; bolt 1 is a distant one.
STRIKES = [(0.0, 0, 1.0), (0.10, 0, 0.75), (0.26, 0, 0.55), (0.52, 0, 0.35),
           (T_HOTTER, 1, 0.65), (T_HOTTER + 0.09, 1, 0.4),
           (T_SUNW, 0, 0.9), (T_SUNW + 0.12, 0, 0.5)]


def flash(te, bolt=None):
    """Brightness of the bolt(s) at loop time te (sharp attack, fast decay)."""
    v = 0.0
    for t0, b, peak in STRIKES:
        if bolt is not None and b != bolt:
            continue
        for shift in (0.0, -DUR):                     # strikes near t=0 are also seen just before the seam
            u = te - (t0 + shift)
            if 0 <= u < 0.5:
                v = max(v, peak * math.exp(-u / 0.045))
    return v


def leader(te):
    """Stepped leader progress 0..1 during the last shot (te < 0), reaching ~0.93 at the seam."""
    s = SHOTS[-1]
    t0 = s[0] - DUR
    if te < t0 + 0.25 or te >= 0:
        return 0.0
    u = (te - (t0 + 0.25)) / (-(t0 + 0.25))
    steps = 14
    return 0.93 * math.floor(u * steps + 1e-6) / steps + 0.93 * 0.35 * ((u * steps) % 1.0) ** 6 / steps


def shake(te):
    """Camera shake after strikes (metres)."""
    a = 0.0
    for t0, b, peak in STRIKES:
        for shift in (0.0, -DUR):
            u = te - (t0 + shift)
            if 0 <= u < 1.2:
                a += (0.10 if b == 0 else 0.04) * peak * math.exp(-u / 0.18)
    return (a * math.sin(te * 71.0), a * 0.4 * math.sin(te * 53.0 + 1), a * 0.7 * math.sin(te * 89.0 + 2))


# ---------------------------------------------------------------- macro set helpers
def shock(t):
    """Shock-wave radius (macro units) after "explodes", and a second one on "thunder"."""
    out = []
    for t0 in (T_EXPL - 0.05, T_THUNDER - 0.05):
        u = t - t0
        if u > 0:
            out.append((0.06 + 1.6 * ease_out(u / 1.6), clamp(1 - u / 1.6)))
    return out



def bolt_path(a, b, rough, n_levels, seed):
    r = np.random.default_rng(seed)
    pts = [np.array(a, float), np.array(b, float)]
    disp = rough
    for _ in range(n_levels):
        new = [pts[0]]
        for p, q in zip(pts, pts[1:]):
            mid = (p + q) / 2
            d = q - p
            side = np.cross(d, [0.3, 1.0, 0.2])
            side /= np.linalg.norm(side) + 1e-9
            side2 = np.cross(d, side)
            side2 /= np.linalg.norm(side2) + 1e-9
            mid = mid + side * r.normal(0, disp) + side2 * r.normal(0, disp * 0.6)
            new += [mid, q]
        pts = new
        disp *= 0.55
    return np.array(pts)


SEG_PATH = bolt_path((MACRO[0] + 0.05, MACRO[1], MACRO[2] + 3.0), (MACRO[0] - 0.05, MACRO[1], MACRO[2] - 3.0), 0.12, 5, 21)
_k = int(np.argmin(np.abs(SEG_PATH[:, 2] - (MACRO[2] + 0.36))))
CH_X, CH_Y = float(SEG_PATH[_k, 0]), float(SEG_PATH[_k, 1])


def _shots():
    l = L
    m = lambda x, y, z: add(MACRO, (x, y, z))
    s_ = lambda x, y, z: add(SUNSET_, (x, y, z))
    e = lambda x, y, z: add(EARTHSET, (x, y, z))
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set
        (0.0, l["heat"][0] - 0.1, (2.2, -15.5, 1.6), (1.8, -12.8, 1.8), (0.6, 0.0, 9.6), (0.5, 0.0, 9.4), 24, 24, "storm"),
        (l["heat"][0] - 0.1, W("sun", "the")[0] - 0.1, m(0.55, -1.25, 0.2), m(0.25, -0.95, 0.45), m(0, 0, 0.1), m(0, 0, 0.4), 40, 40, "macro"),
        (W("sun", "the")[0] - 0.1, l["boom"][0] - 0.1, s_(0.0, -5.0, 0.9), s_(0.0, -4.2, 0.7), s_(0, 0, 0.2), s_(0, 0, 0.1), 40, 40, "sun"),
        (l["boom"][0] - 0.1, l["inch"][0] - 0.1, m(0.9, -3.2, 1.9), m(0.7, -2.8, 1.7), m(0, 0, 0.0), m(0, 0, 0.1), 32, 32, "macro"),
        (l["inch"][0] - 0.1, l["count"][0] - 0.1, (CH_X + 0.03, CH_Y - 0.30, MACRO[2] + 0.40), (CH_X + 0.02, CH_Y - 0.26, MACRO[2] + 0.39), (CH_X, CH_Y, MACRO[2] + 0.36), (CH_X, CH_Y, MACRO[2] + 0.36), 60, 60, "macro"),
        (l["count"][0] - 0.1, l["loop"][0] - 0.12, e(1.2, -3.6, 1.3), e(0.8, -3.0, 0.9), e(0, 0, 0.1), e(0, 0, 0.05), 32, 32, "earth"),
        (l["loop"][0] - 0.12, DUR, (4.0, -21.0, 2.2), None, (0.8, 0.0, 9.8), None, 24, 24, "storm"),
    ]


SHOTS = _shots()


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


def shot_set(t):
    return SHOTS[shot_index(t)][8]


def env_t(t):
    """Storm clock: in the last shot it runs up to 0, so the final frame flows into frame 0 (the strike)."""
    return t - DUR if shot_index(t) == len(SHOTS) - 1 else t


CAM0_K = 0.9


def cam0(te):
    s0 = SHOTS[0]
    f = (1 - math.exp(-CAM0_K * te)) / (1 - math.exp(-CAM0_K * s0[1]))
    return lerpv(s0[2], s0[3], f), lerpv(s0[4], s0[5], f), s0[6]


def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1, _set = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == 0:
        p, a, l_ = cam0(t)
    elif i == len(SHOTS) - 1:
        cp, ct, cl = cam0(env_t(t))
        w = smoother(x / 0.8)
        p, a, l_ = lerpv(p0, cp, w), lerpv(a0, ct, w), lerp(l0, cl, w)
    else:
        u = smoother(x) * 0.85 + 0.15 * x
        p, a, l_ = lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)
    if _set == "storm":
        p = add(p, shake(env_t(t)))
    if i == 3:                                     # the shock wave jolts the camera
        for t_ in (T_EXPL, T_THUNDER):
            u = t - t_
            if 0 < u < 0.8:
                k = 0.05 * math.exp(-u / 0.15)
                p = add(p, (k * math.sin(u * 80), 0, k * math.sin(u * 63)))
    return p, a, l_
