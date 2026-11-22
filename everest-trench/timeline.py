"""Shot timeline for "Mount Everest Would Vanish in the Mariana Trench", derived from the narration timing.

Units: 1 scene unit = 1 km horizontally; heights are exaggerated VE times (the same for every object).
Sets (one Blender scene):
  tank:  a cut-away block of the real Mariana Trench (Challenger Deep in the middle) under a block of water,
         sea level at z = 0, and a chunk of the real Mount Everest that is dropped into it.
  macro: the trench floor at inch scale (1 unit = 1 inch) for the pressure shot, at MACRO.
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
NFRAMES = round((L["loop"][1] + 0.07) * FPS)
DUR = NFRAMES / FPS

VE = 2.5                         # vertical exaggeration
KM = VE                          # 1 km of height in scene units
FT = 0.0003048 * VE              # 1 foot of height in scene units
DEEP_FT = 35876                  # Challenger Deep
EVEREST_FT = 29032
FLOOR_Z = -10.891 * KM           # deepest point of the trench data (centre of the tank)
HALF = 30.0                      # tank half-size (km)
MACRO = (500.0, 0.0, 0.0)


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


T_DROP = W("hook", "drop")[0]
T_NEVER = W("hook", "never")[0]
T_TRENCH = W("deep", "trench")[0]
T_7 = W("deep", "7")[0]
T_SINK = W("cover", "sink")[0]
T_MILE = W("cover", "mile")[0]
T_PEAK = W("cover", "peak")[0]
T_SUN = W("dark", "sunlight")[0]
T_3000 = W("dark", "3000")[0]
T_BOTTOM = W("pressure", "bottom")[0]
T_8 = W("pressure", "8")[0]
T_SQUARE = W("pressure", "square")[0]
T_DEEPW = W("loop", "deep")[0]

# ---------------------------------------------------------------- Everest's fall (loop clock te)
# The chunk's lowest point (its root tip) hits the water at te = 0 with speed V_HIT, free-falls before that
# and sinks with drag after it, settling on the trench floor. Defined for te < 0 so the last shot flows into frame 0.
V_HIT = 19.0
G_FALL = 9.0
REST_Z = FLOOR_Z + 0.6           # the tip rests slightly above the deepest point (sunk into the sediment)


def tip_z(te):
    if te < 0:
        return -V_HIT * te - 0.5 * G_FALL * te * te
    d = -REST_Z
    return -d * (1 - math.exp(-V_HIT * te / d))


def splash(te):
    """0..1 age of the splash after the impact at te = 0 (None before)."""
    return None if te < 0 or te > 3.0 else te / 3.0


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    m = lambda x, y, z: add(MACRO, (x, y, z))
    s3 = l["dark"][0] - 0.12
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, set
        # S0 hook: the chunk of Everest plunges into the ocean at frame 0 and sinks out of sight
        (0.0, l["deep"][0] - 0.1, (40.0, -84.0, 30.0), (34.0, -72.0, 19.0), (0.0, 0.0, -1.0), (0.0, 0.0, -9.0), 30, 30, "tank"),
        # S1 how deep: the camera sinks along the cut face next to a depth gauge
        (l["deep"][0] - 0.1, l["cover"][0] - 0.1, (20.0, -50.0, -2.0), (17.0, -46.0, -13.0), (3.0, 0.0, -3.0), (3.0, 0.0, -21.0), 32, 32, "tank"),
        # S2 Everest on the floor: over a mile of water above its peak
        (l["cover"][0] - 0.1, s3, (9.0, -34.0, -3.0), (8.0, -30.0, -1.2), (0.0, 0.0, -11.0), (0.0, 0.0, -6.5), 30, 30, "tank"),
        # S3 sunlight fades out in the top 3,000 ft
        (s3, l["pressure"][0] - 0.1, (6.0, -46.0, 4.0), (5.0, -42.0, -3.5), (0.0, 0.0, -1.0), (0.0, 0.0, -5.0), 34, 34, "tank"),
        # S4 the pressure on the trench floor: 8 tons on one square inch
        (l["pressure"][0] - 0.1, l["loop"][0] - 0.12, m(1.2, -6.0, 1.9), m(5.5, -21.0, 6.5), m(0.0, 0.0, 0.9), m(0.0, 0.0, 3.4), 40, 40, "macro"),
        # S5 last shot: Everest falls in from the sky again and the camera glides into the opening framing
        (l["loop"][0] - 0.12, DUR, (34.0, -78.0, 26.0), None, (0.0, 0.0, 4.0), None, 30, 30, "tank"),
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
        return cam0(t)
    if i == len(SHOTS) - 1:
        cp, ct, cl = cam0(env_t(t))
        w = smoother(x / 0.85)
        return lerpv(p0, cp, w), lerpv(a0, ct, w), lerp(l0, cl, w)
    if _set == "macro":                     # close on the square inch, pull back as the weight lands
        u = 0.08 * x + 0.92 * smoother((t - T_8 + 0.05) / 0.9)
        return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)
    u = smoother(x) * 0.85 + 0.15 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lerp(l0, l1, u)
