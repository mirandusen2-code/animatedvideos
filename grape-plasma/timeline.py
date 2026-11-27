"""Shot timeline for "Grapes in a microwave make plasma", derived from the narration timing (1 unit = 1 inch).

The plasma burst in the microwave runs on its own clock (burst time te): frame 0 is RE0 s after the burst; the loop
shot runs at negative te (the grapes start to spark) and flows straight into frame 0. Picture and sound read the same
event functions below.
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
T_PUT, T_GRAPES, T_MICRO, T_SPIT, T_BALL, T_PLASMA0 = (W("hook", w) for w in
                                                      ("put", "grapes", "microwave", "spit", "ball", "plasma"))
T_WHY, T_PHYS, T_SQUEEZE, T_LIGHT, T_TINY, T_GDO = (W("why", w) for w in
                                                    ("why", "physicists", "squeeze", "light", "tiny", "grapes"))
T_MICRO2, T_5, T_LONG = W("wave", "microwave"), W("wave", "5"), W("wave", "long")
T_WATER, T_SHRINKS, T_HALF, T_INCH, T_GSIZE = (W("water", w) for w in ("water", "shrinks", "half", "inch", "grape"))
T_EACH, T_TRAPS, T_WAVES, T_BOUNCE, T_INSIDE = (W("trap", w) for w in ("each", "traps", "waves", "bounce", "inside"))
T_TWO, T_TOUCH, T_PILES, T_SPOT, T_PIN = (W("touch", w) for w in ("two", "touch", "piles", "spot", "pinhead"))
T_RIPS, T_ELEC, T_SALT, T_JUICE, T_BOOM, T_PLASMA = (W("plasma", w) for w in
                                                     ("rips", "electrons", "salt", "juice", "boom", "plasma"))
T_PROVED, T_BEADS, T_NOSKIN, T_SAME, T_FIRE = W("proof", "proved"), W("proof", "beads"), W("proof", "no"), \
    W("proof", "same"), W("proof", "fireball")
T_SO, T_NEVER, T_HOME = W("loop", "so"), W("loop", "never"), W("loop", "home")

# ---------------------------------------------------------------- shot cut times
C1 = T_MICRO[0] - 0.08                       # fireball close-up -> the whole oven
C2 = L["hook"][1] + 0.12                     # -> lab: light squeezed into a tiny spot (why)
C2B = T_TINY[0] - 0.12                       # -> close on the touching point: the tiny spot
C3 = L["why"][1] + 0.12                      # -> one microwave, 5 inches long
C4 = L["wave"][1] + 0.1                      # -> into water: it shrinks to grape size
C5 = L["water"][1] + 0.12                    # -> a cut-away grape: the waves bounce inside
C6 = L["trap"][1] + 0.12                     # -> two grapes touching: the hotspot, a pinhead
C7 = L["touch"][1] + 0.12                    # -> zoom: salt ions, electrons ripped off, plasma
C8 = L["plasma"][1] + 0.12                   # -> the microwave again: water beads
C9 = L["proof"][1] + 0.12                    # -> loop: grapes on the turntable start to spark

RE0 = 0.22                                   # frame 0 shows the fireball 0.22 s after the burst
T_BURST8 = T_SAME[0] - 0.12                  # the water beads burst on "same"
T_RIP = T_RIPS[0] + 0.05                     # electrons start to fly off in the zoom
T_BOOM7 = T_BOOM[0] - 0.03                   # the zoom plasma flashes on "boom"
E_T0 = np.random.default_rng(78).uniform(0.0, 0.5, 18)   # when each electron is ripped off (after T_RIP)

LO = tuple(G.LAB_O)
GP = tuple(G.LAB_O + G.LAB_GRAPES + np.array([0, 0, G.LAB_GZ]))        # lab contact point
ZO = tuple(G.ZOOM_O)
CT = tuple(G.contact(G.MW_O))


def _shots():
    return [
        # t0, t1, set, loc0, loc1, tgt0, tgt1, lens
        (0.0, C1, "mw", None, None, None, None, 35),
        (C1, C2, "mw", add(CT, (-2.4, -12.0, 2.6)), add(CT, (-1.4, -8.6, 3.4)), add(CT, (0, 0, 1.9)),
         add(CT, (0, 0, 3.4)), 26),
        (C2, C2B, "lab", add(GP, (-1.2, -9.5, 1.6)), add(GP, (-0.9, -7.6, 1.2)), add(GP, (-1.6, 0, 0.6)),
         add(GP, (-1.1, 0, 0.4)), 32),
        (C2B, C3, "lab", add(GP, (0.9, -3.0, 0.7)), add(GP, (0.6, -2.3, 0.45)), add(GP, (0.0, 0, 0.05)),
         add(GP, (0.0, 0, 0.02)), 35),
        (C3, C4, "lab", add(LO, (-1.0, -17.0, 3.6)), add(LO, (-0.6, -15.5, 3.4)), add(LO, (-1.0, 0, 2.7)),
         add(LO, (-0.6, 0, 2.7)), 30),
        (C4, C5, "lab", add(LO, (2.0, -14.5, 3.5)), add(LO, (4.6, -8.0, 3.4)), add(LO, (3.0, 0, 2.9)),
         add(LO, (4.7, 0, 3.0)), 30),
        (C5, C6, "lab", add(GP, (0.75, -4.6, 0.75)), add(GP, (0.6, -3.7, 0.55)), add(GP, (0.4, 0, 0.0)),
         add(GP, (0.4, 0, 0.0)), 35),
        (C6, C7, "lab", add(GP, (0.15, -5.2, 1.0)), add(GP, (0.05, -1.7, 0.25)), add(GP, (0, 0, 0.0)),
         add(GP, (0, 0, 0.0)), 35),
        (C7, C8, "zoom", add(ZO, (0.3, -5.6, 0.9)), add(ZO, (0.0, -7.2, 0.6)), add(ZO, (0, 0, 0.35)),
         add(ZO, (0, 0, 0.6)), 30),
        (C8, C9, "mw", add(CT, (-1.8, -6.6, 1.8)), add(CT, (-1.6, -5.6, 2.2)), add(CT, (0, 0, 0.5)),
         add(CT, (0, 0, 1.2)), 30),
        (C9, DUR, "mw", None, None, None, None, 35),
    ]


SHOTS = _shots()
S_WHY, S_WAVE, S_WATER, S_TRAP, S_TOUCH, S_ZOOM, S_BEADS = (2, 3), 4, 5, 6, 7, 8, 9
SET_OF = [s[2] for s in SHOTS]
LOOP_I = len(SHOTS) - 1


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if t < s[1]:
            return i
    return len(SHOTS) - 1


# ---------------------------------------------------------------- clocks / states
def burst_clock(t):
    """Time since the grapes burst into plasma (frame 0 = RE0); negative in the loop shot."""
    i = shot_index(t)
    if i in (0, 1):
        return t + RE0
    if i == LOOP_I:
        return t - DUR + RE0
    if i == S_BEADS:
        return t - T_BURST8
    return None


def mw_state(t):
    """(te since the burst, beads instead of grapes?, turntable angle)."""
    te = burst_clock(t)
    beads = shot_index(t) == S_BEADS
    return te, beads, G.TT_W * (te if not beads else t)


# ---------------------------------------------------------------- cameras
CAM0_LOC = np.array(CT) + np.array([-1.55, -3.55, 0.55])
CAM0_VEL = np.array([-0.10, -0.32, 0.05])
CAM0_TGT = np.array(CT) + np.array([0.0, 0.0, 0.42])


def cam0(t):
    """Hook camera; linear in t, so it is smooth when evaluated at negative time in the loop shot."""
    return tuple(CAM0_LOC + CAM0_VEL * t), tuple(CAM0_TGT + np.array([0.0, 0.0, 0.10]) * t), 35.0


WIDE_LOC = np.array(CT) + np.array([-2.2, -10.5, 2.6])
WIDE_TGT = np.array(CT) + np.array([0.0, 0.0, 1.0])


def camera(t):
    i = shot_index(t)
    t0, t1, _s, p0, p1, a0, a1, lens = SHOTS[i]
    if i == 0:
        return cam0(t)
    if i == LOOP_I:
        tn = t - DUR
        loc, tgt, ln = cam0(tn)
        w = smoother((tn - (t0 - DUR) - 0.1) / (-(t0 - DUR) - 0.45))   # wide oven -> hook camera, pure by tn ~ -0.35
        return (tuple(lerp(a, b, w) for a, b in zip(WIDE_LOC, loc)),
                tuple(lerp(a, b, w) for a, b in zip(WIDE_TGT, tgt)), lerp(26.0, ln, w))
    x = clamp((t - t0) / (t1 - t0))
    u = smoother(x) * 0.6 + 0.4 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lens


def shake(t):
    i = shot_index(t)
    te = burst_clock(t)
    if i in (0, S_BEADS) and te is not None and te > 0:
        return 0.025 * math.exp(-te / 0.3)
    if i == S_ZOOM:
        a = t - T_BOOM7
        return 0.05 * math.exp(-a / 0.3) if a > 0 else 0.0
    return 0.0


if __name__ == "__main__":
    print("NFRAMES", NFRAMES, "DUR", round(DUR, 2))
    for k, s in enumerate(SHOTS):
        print(k, s[2], round(s[0], 2), round(s[1], 2), int(math.ceil(s[0] * FPS - 1e-9)))
    for f in list(range(NFRAMES - 75, NFRAMES, 5)) + [NFRAMES - 1]:
        l, g, ln = camera(f / FPS)
        print(f, [round(c, 2) for c in l], round(ln, 1), mw_state(f / FPS))
    print(0, [round(c, 2) for c in camera(0)[0]])
