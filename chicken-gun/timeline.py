"""Shot timeline for "Engineers Fire Chickens at Airplanes", derived from the narration timing (1 unit = 1 ft).

Each shot uses one set (SET_OF). The main impact runs on its own clock (imp_clock, slow motion): the loop shot runs at
negative time (the chicken leaves the muzzle and flies in) and flows straight into frame 0 (feathers bursting).
Picture and sound read the same event functions below.
"""
import json
import math
import os
import re

import numpy as np

import geo as G

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
NFRAMES = round((L["loop"][1] + 0.07) * FPS)
DUR = NFRAMES / FPS


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


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(*v):
    return tuple(float(sum(c)) for c in zip(*v))


# ---------------------------------------------------------------- word times
T_FIRE, T_CHICK, T_AIRP, T_350, T_MPH = W("hook", "fire"), W("hook", "chickens"), W("hook", "airplanes"), \
    W("hook", "350"), W("hook", "miles")
T_WHY, T_BIRDS, T_HIT, T_PLANES = W("why", "why"), W("why", "birds"), W("why", "hit"), W("why", "planes")
T_60, T_DAY, T_US = W("why", "60"), W("why", "day"), W("why", "us")
T_2009, T_GEESE, T_SHUT, T_BOTH, T_ENG = W("hudson", "2009"), W("hudson", "geese"), W("hudson", "shut"), \
    W("hudson", "both"), W("hudson", "engines")
T_JET, T_NY = W("hudson", "jet"), W("hudson", "new")
T_FIRST, T_WIND, T_BROKE, T_75 = W("old", "first"), W("old", "windshields"), W("old", "broke"), W("old", "75")
T_COCK, T_WINDOW, T_STOP, T_4LB, T_BIRD = W("rule", "cockpit"), W("rule", "window"), W("rule", "stop"), \
    W("rule", "4pound"), W("rule", "bird")
T_TEST, T_REAL, T_FIRED, T_GIANT, T_CANNON = W("gun", "test"), W("gun", "real"), W("gun", "fired"), \
    W("gun", "giant"), W("gun", "cannon")
T_ONE, T_RULE, T_CANT, T_FROZEN, T_RBIRDS, T_ICE = W("twist", "one"), W("twist", "rule"), W("twist", "cant"), \
    W("twist", "frozen"), W("twist", "birds"), W("twist", "ice")
T_THATS, T_FLY = W("loop", "thats"), W("loop", "fly")

# ---------------------------------------------------------------- impact clock constants
TE0 = 0.08                         # frame 0 shows the impact 0.08 s (slow-motion time) after contact
V_IN = 26.0                        # chicken speed on screen (ft/s, slow motion)
T_MUZZLE = (45.0 - 0.62) / V_IN    # flight time from the muzzle to the pane

PI_ = tuple(G.P_I)
SK = tuple(G.SKY_O)
OC = tuple(G.OLD_O + np.array([0.0, 0.0, 6.0]))
SO = tuple(G.SCALE_O + np.array([0.0, 0.0, 3.0]))
FO = tuple(G.FROZ_O + np.array([0.0, 0.0, 3.0]))
BR = tuple(G.BREECH)
MZ = tuple(G.MUZZLE)

# shot cut times
C1 = T_AIRP[0] - 0.02                       # hook close-up -> wide rig
C2 = L["hook"][1] + 0.12                    # -> sky (why)
C3 = L["why"][1] + 0.12                     # -> New York
C4 = L["hudson"][1] + 0.12                  # -> old windshield
C5 = L["old"][1] + 0.12                     # -> cockpit window (rule)
C6 = T_STOP[0] - 0.05                       # -> scale
C7 = L["rule"][1] + 0.12                    # -> breech
C8 = T_FIRED[0] - 0.04                      # -> muzzle
C9 = L["gun"][1] + 0.12                     # -> frozen
C10 = L["twist"][1] + 0.12                  # -> loop (lab)

SKY_HITS = [T_BIRDS[0] + 0.1 - C2, T_PLANES[0] + 0.15 - C2, T_DAY[0] - C2]
ENG_HITS = [T_SHUT[0] + 0.05 - C3, T_ENG[0] + 0.05 - C3]
T_OLD_HIT = T_BROKE[0] + 0.02
T_LAND = T_4LB[0] + 0.05
T_LOAD = T_TEST[0] - 0.05
T_SHOT = T_CANNON[0] - 0.12
T_DROP = T_ONE[0] + 0.25
T_MELT = T_RBIRDS[0] - 0.45


def _shots():
    o = PI_
    return [
        # t0, t1, set, loc0, loc1, tgt0, tgt1, lens
        (0.0, C1, "lab", None, None, None, None, 28),
        (C1, C2, "lab", add(o, (-5, -70, 4.0)), add(o, (-4.5, -47, 3.0)), add(o, (0, -5, -1)), add(o, (0, 0, -0.5)), 32),
        (C2, C3, "sky", add(SK, (-24, -42, 7)), add(SK, (-18, -31, 4.5)), add(SK, (0, 10, 0)), add(SK, (0, 6, 0)), 30),
        (C3, C4, "sky", add(SK, (-80, -36, 46)), add(SK, (-68, -14, 38)), add(SK, (0, 34, -8)), add(SK, (0, 30, -9)), 30),
        (C4, C5, "old", add(OC, (2.2, 7.5, 0.6)), add(OC, (1.8, 6.0, 0.4)), add(OC, (0, -4, 0)), add(OC, (0.3, -2, 0)), 32),
        (C5, C6, "lab", add(o, (-11, -15, 3.5)), add(o, (-8, -11, 2.6)), add(o, (1.5, 2.5, -1.5)), add(o, (1.5, 2.5, -1.2)), 30),
        (C6, C7, "scale", add(SO, (-3.6, -5.6, 2.6)), add(SO, (-2.6, -4.3, 2.0)), add(SO, (0, 0.3, 0.9)), add(SO, (0, 0.3, 0.8)), 35),
        (C7, C8, "gun", add(BR, (-3.4, -6.2, 1.7)), add(BR, (-2.4, -4.3, 1.1)), add(BR, (0, 1.2, 0)), add(BR, (0, 2.0, 0)), 30),
        (C8, C9, "gun", add(MZ, (-6.5, 8.0, 1.6)), add(MZ, (-6.0, 11.0, 1.2)), add(MZ, (0, 1.5, 0)), add(MZ, (0, 5, 0)), 24),
        (C9, C10, "froz", add(FO, (-3.3, -5.1, 2.4)), add(FO, (-2.5, -3.9, 1.8)), add(FO, (0, 0, 0.75)), add(FO, (0, 0, 0.7)), 38),
        (C10, DUR, "lab", None, None, None, None, 28),
    ]


SHOTS = _shots()
SET_OF = [s[2] for s in SHOTS]
LOOP_I = len(SHOTS) - 1


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if t < s[1]:
            return i
    return len(SHOTS) - 1


def imp_clock(t):
    """Slow-motion time since chicken A touched the cockpit pane (None outside the lab shots that show it)."""
    i = shot_index(t)
    if i in (0, 1):
        return t + TE0
    if i == LOOP_I:
        return t - DUR + TE0
    return None


def lab_fire_clock(t):
    """Time since chicken A left the muzzle (the loop shot), for the muzzle puff."""
    te = imp_clock(t)
    if te is None or shot_index(t) != LOOP_I:
        return None
    return te + T_MUZZLE


def old_clock(t):
    return t - T_OLD_HIT if shot_index(t) == 4 else None


def scale_clock(t):
    return t - T_LAND if shot_index(t) == 6 else None


def gun_clocks(t):
    i = shot_index(t)
    if i not in (7, 8):
        return None, None
    return t - T_LOAD, (t - T_SHOT if i == 8 else -9.0)


def froz_clocks(t):
    if shot_index(t) != 9:
        return None, None
    return t - T_DROP, t - T_MELT


def sky_clock(t):
    i = shot_index(t)
    if i == 2:
        return "gulls", t - C2
    if i == 3:
        return "geese", t - C3
    return "gulls", 0.0


# ---------------------------------------------------------------- cameras
CAM0_LOC = np.array(add(PI_, (-3.2, -5.6, 3.3)))
CAM0_VEL = np.array([-0.2, -0.45, 0.28])           # slow pull back while the feathers fly at the lens
CAM0_TGT = np.array(add(PI_, (0.1, 0.4, -0.35)))
SIDE_LOC = np.array(add(PI_, (-7, -66, 4.0)))
SIDE_TGT = np.array(add(PI_, (0, -20, -0.5)))


def cam0(t):
    """Hook camera; linear in t, so it is smooth when evaluated at negative time in the loop shot."""
    return tuple(CAM0_LOC + CAM0_VEL * t), tuple(CAM0_TGT + np.array([0.0, 0.1, 0.05]) * t), 30.0


def camera(t):
    i = shot_index(t)
    t0, t1, _s, p0, p1, a0, a1, lens = SHOTS[i]
    if i == 0:
        return cam0(t)
    if i == LOOP_I:
        tn = t - DUR
        loc, tgt, ln = cam0(tn)
        w = smoother((tn + 1.75) / 1.25)            # side view of the rig -> hook camera (pure by tn = -0.5)
        side_l = SIDE_LOC + np.array([0.0, 6.0, 0.0]) * (tn + 2.2)
        return (tuple(lerp(a, b, w) for a, b in zip(side_l, loc)),
                tuple(lerp(a, b, w) for a, b in zip(SIDE_TGT, tgt)), lerp(26.0, ln, w))
    x = clamp((t - t0) / (t1 - t0))
    u = smoother(x) * 0.6 + 0.4 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lens


def shake(t):
    i = shot_index(t)
    te = imp_clock(t)
    if i == 0 and te is not None:
        return 0.05 * math.exp(-te / 0.25)
    if i == 4:
        a = t - T_OLD_HIT
        return 0.04 * math.exp(-a / 0.3) if a > 0 else 0.0
    if i == 9:
        a = t - T_DROP
        return 0.03 * math.exp(-a / 0.2) if a > 0 else 0.0
    return 0.0


if __name__ == "__main__":
    print("NFRAMES", NFRAMES, "DUR", round(DUR, 2))
    for k, s in enumerate(SHOTS):
        print(k, s[2], round(s[0], 2), round(s[1], 2), int(s[0] * FPS))
    print("SKY_HITS", [round(x, 2) for x in SKY_HITS], "ENG_HITS", [round(x, 2) for x in ENG_HITS])
    for f in range(NFRAMES - 75, NFRAMES):
        l, g, ln = camera(f / FPS)
        print(f, [round(c, 2) for c in l], round(ln, 1))
    print(0, [round(c, 2) for c in camera(0)[0]])
