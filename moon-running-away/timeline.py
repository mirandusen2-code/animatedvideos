"""Shot timeline for "The Moon Is Running Away From Us", derived from the narration timing (vo/timing.json).

Sets (one Blender scene):
  earth:   Earth (radius 1) at the origin and the Moon receding from it (opening, laser, young Earth spin, loop).
  surface: a macro of the Apollo retroreflector on the lunar surface, at SURF.
  young:   the surface of the young Earth with a giant Moon in the sky, at YOUNG.
  eclipse: the Sun and the Moon seen from Earth, at ECL.
"""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
NFRAMES = round((L["loop"][1] + 0.05) * FPS)
DUR = NFRAMES / FPS

SURF = (500.0, 0.0, 0.0)
YOUNG = (1000.0, 0.0, 0.0)
ECL = (1500.0, 0.0, 0.0)

MOON_R = 0.38
MOON_DIR = (0.15, 0.30, 0.94)          # direction from Earth to the Moon (normalised in moon_pos)


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


T_YEAR = W("rate", "year")[0]
T_INCH = W("rate", "15")[0]
T_NAILS = W("nails", "fingernails")[0]
T_BORN = W("past", "born")[0]
T_SKY = W("past", "sky")[0]
T_DAY = W("day", "day")[0]
T_HOURS = W("day", "6")[0]
T_600 = W("eclipse", "600")[0]
T_FAR = W("eclipse", "far")[0]
T_SUN = W("eclipse", "sun")[0]
T_LEAVING = W("loop", "leaving")[0]


# ---------------------------------------------------------------- the receding Moon (opening + loop)
D0 = 4.5                               # Earth-Moon distance at the loop point (stylised; Earth radius = 1)
D_K = 0.32                             # exponential recession rate of the time-lapse


def moon_dist(te):
    """Defined for negative loop time too, so the last shot hands over with no jump in distance or speed."""
    return D0 * math.exp(D_K * te)


def moon_pos(te):
    n = math.sqrt(sum(c * c for c in MOON_DIR))
    d = moon_dist(te)
    return tuple(c / n * d for c in MOON_DIR)


def miles(te):
    """Distance read-out: 238,855 mi at the seam, climbing (stylised time-lapse)."""
    return 238855 + 9000 * (moon_dist(te) - D0)


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    s = lambda x, y, z: add(SURF, (x, y, z))
    y_ = lambda x, y, z: add(YOUNG, (x, y, z))
    e = lambda x, y, z: add(ECL, (x, y, z))
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set
        # S0 hook: over Earth's limb, the Moon flies away (camera pulls back fast from frame 0; see cam0)
        (0.0, l["rate"][0] - 0.1, (0.7, -2.6, 0.15), (0.8, -3.5, 0.25), (0.45, 0.6, 2.2), (0.5, 0.7, 2.6), 28, 28, "earth"),
        # S1 the laser: a pulse fires from Earth to the Moon and back (side view)
        (l["rate"][0] - 0.1, l["nails"][0] - 0.1, (7.5, -9.0, 3.0), (6.8, -8.2, 3.0), (0.5, 0.9, 2.9), (0.5, 0.9, 2.9), 30, 30, "earth"),
        # S2 macro: the Apollo retroreflector on the lunar surface
        (l["nails"][0] - 0.1, l["past"][0] - 0.1, s(0.55, -1.25, 0.32), s(0.45, -1.05, 0.30), s(0, 0, 0.35), s(0, 0, 0.38), 30, 30, "surface"),
        # S3 the young Earth: a giant Moon fills the sky
        (l["past"][0] - 0.1, l["day"][0] - 0.05, y_(0.0, -6.0, 1.4), y_(0.0, -5.2, 1.2), y_(0.0, 10.0, 7.5), y_(0.0, 10.0, 8.0), 22, 22, "young"),
        # S4 the young Earth spins fast: a 6-hour day (the Moon close behind)
        (l["day"][0] - 0.05, l["eclipse"][0] - 0.1, (3.3, -2.0, 1.3), (3.0, -1.8, 1.2), (0.2, 0.4, 1.05), (0.2, 0.4, 1.05), 30, 30, "earth"),
        # S5 eclipse: total now, then a ring as the Moon shrinks
        (l["eclipse"][0] - 0.1, l["loop"][0] - 0.12, e(0, 19.0, 0), e(0, 19.4, 0), e(0, 40, 0), e(0, 40, 0), 50, 50, "eclipse"),
        # S6 last shot glides back into the opening framing (match cut into frame 0)
        (l["loop"][0] - 0.12, DUR, (2.8, -4.2, 1.0), None, (0.6, 0.8, 2.4), None, 26, 28, "earth"),
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
    return t - DUR if shot_index(t) == len(SHOTS) - 1 else t


CAM0_K = 1.0


def cam0(te):
    s0 = SHOTS[0]
    f = (1 - math.exp(-CAM0_K * te)) / (1 - math.exp(-CAM0_K * s0[1]))
    return lerpv(s0[2], s0[3], f), lerpv(s0[4], s0[5], f), s0[6]


def camera(t):
    i = shot_index(t)
    t0, t1, p0, p1, a0, a1, l0, l1, _set = SHOTS[i]
    x = clamp((t - t0) / (t1 - t0))
    if i == 0:
        return cam0(t)
    if i == len(SHOTS) - 1:
        cp, ct, cl = cam0(env_t(t))
        w = smoother(x / 0.85)
        return lerpv(p0, cp, w), lerpv(a0, ct, w), lerp(l0, cl, w)
    u = smoother(x) * 0.85 + 0.15 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)
