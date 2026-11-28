"""Shot timeline for "Mentos + Diet Coke", derived from the narration timing (1 unit = 1 inch).

The hero geyser runs on its own clock (te, time since it starts to erupt): frame 0 is RE0 s into the eruption; the
loop shot runs at negative te (the Mentos fall into the bottle) and flows straight into frame 0. Picture and sound
read the same event functions below.
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
        if a - 0.01 <= s <= b + 0.01 and re.sub(r"[^a-z0-9]", "", w.lower()).startswith(word.lower()):
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
T_DROP, T_MENTOS0, T_DIET0W, T_BLASTS, T_HIGHER, T_HOOP = (W("hook", w) for w in
                                                            ("drop", "mentos", "diet", "blasts", "higher", "hoop"))
T_WHY, T_BOTTLE, T_SECRET, T_HOLD, T_3, T_GAS = (W("why", w) for w in
                                                 ("why", "bottle", "secretly", "holding", "3", "gas"))
T_FACTORY, T_SQUEEZED, T_DYING, T_GETOUT = (W("squeeze", w) for w in ("factory", "squeezed", "dying", "get"))
T_BUBBLE, T_CANT, T_NOTHING, T_NEEDS, T_ROUGH, T_SPOT = (W("seed", w) for w in
                                                         ("bubble", "can", "nothing", "needs", "rough", "spot"))
T_UPCLOSE, T_MENTOS4, T_COVERED, T_TINY, T_CRATERS = (W("pits", w) for w in
                                                      ("up", "mentos", "covered", "tiny", "craters"))
T_EVERY, T_SPITS, T_BUBBLES, T_ALL, T_ONCE = (W("bubbles", w) for w in ("every", "spits", "bubbles", "all", "once"))
T_HEAVY, T_SINK, T_MAKING, T_WAYDOWN = W("sink", "heavy"), W("sink", "sink"), W("sink", "making"), W("sink", "down")
T_FOAM, T_ONEWAY, T_UP = W("push", "foam"), W("push", "one"), W("push", "up")
T_DIETW, T_BEST, T_SWEET, T_EASIER = (W("diet", w) for w in ("diet", "best", "sweetener", "easier"))
T_STAND, T_BACK = W("loop", "stand"), W("loop", "back")

# ---------------------------------------------------------------- shot cut times
C1 = T_BLASTS[0] - 0.08                      # geyser close-up -> wide: higher than the hoop
C2 = L["hook"][1] + 0.12                     # -> lab: the bottle holds three bottles of gas (why)
C3 = L["why"][1] + 0.12                      # -> the gas squeezed in, dying to get out
C4 = L["squeeze"][1] + 0.12                  # -> micro: a bubble can't start from nothing; the rough spot
C5 = L["seed"][1] + 0.12                     # -> a Mentos, up close
C5B = T_COVERED[0] - 0.1                     # -> micro: covered in craters
C6 = L["pits"][1] + 0.1                      # -> every crater spits out bubbles
C7 = L["bubbles"][1] + 0.12                  # -> lab: the Mentos sink, bubbles all the way down
C8 = L["sink"][1] + 0.12                     # -> the foam has one way out: up
C9 = L["push"][1] + 0.12                     # -> yard: regular vs diet
C10 = L["diet"][1] + 0.12                    # -> loop: the Mentos fall into the bottle

RE0 = 0.30                                   # frame 0 shows the geyser 0.30 s into the eruption
T_DIET_GO = T_BEST[0] - 0.95                 # the two comparison bottles erupt (apex on "best")
T_LOOP_DROP = -0.74                          # (te) the Mentos are let go above the neck in the loop shot

# lab events
T_GHOST = T_3[0] - 0.35                      # three ghost bottles of gas come out of the bottle
T_SQZ = [T_SQUEEZED[0] - 0.15 + 0.17 * k for k in range(3)]   # each ghost bottle slams back in
T_CAP = T_SQUEEZED[1] + 0.05                 # the cap screws on
T_JITTER = T_DYING[0] - 0.1                  # the gas rattles, the bottle strains
T_SINK0 = C7 + 0.15                          # the first Mentos drops into the neck
MENTOS_DT = 0.13                             # between Mentos
T_JET_LAB = T_UP[0] - 0.05                   # the foam jet bursts out of the lab bottle

# micro events
T_FAIL = [T_CANT[0] - 0.05, T_NOTHING[0] + 0.05]   # a bubble tries to start in open soda and collapses
T_HERO = T_ROUGH[0] - 0.1                    # the bubble grows in the rough spot
T_ALLON = T_SPITS[0] - 0.05                  # every crater starts spitting bubbles (stagger 0.12 s)

YO = tuple(G.YARD_O)
LO = tuple(G.LAB_O)
MO = tuple(G.MICRO_O)


def _shots():
    return [
        # t0, t1, set, loc0, loc1, tgt0, tgt1, lens
        (0.0, C1, "yard", None, None, None, None, 24),
        (C1, C2, "yard", add(YO, (30, -100, 14)), add(YO, (27, -120, 22)), add(YO, (13, 0, 70)),
         add(YO, (13, 0, 84)), 18),
        (C2, C3, "lab", add(LO, (2.0, -30, 12)), add(LO, (1.2, -40, 14.5)), add(LO, (0, 0, 8.5)),
         add(LO, (0, 2, 12.5)), 35),
        (C3, C4, "lab", add(LO, (1.5, -40, 14.5)), add(LO, (0.8, -27, 10.5)), add(LO, (0, 2, 12.0)),
         add(LO, (0, 0, 7.5)), 35),
        (C4, C5, "micro", add(MO, (-3, -30, 22)), add(MO, (1, -24, 9)), add(MO, (-2, 0, 14)),
         add(MO, (2, 0, 1.5)), 32),
        (C5, C5B, "lab", add(LO, (60.4, -4.4, 7.0)), add(LO, (60.1, -1.7, 6.3)), add(LO, (60, 0, 6.0)),
         add(LO, (60, 0, 6.0)), 40),
        (C5B, C6, "micro", add(MO, (0, -9, 36)), add(MO, (0, -16, 24)), add(MO, (0, 0, 0)), add(MO, (0, 1, 0)), 30),
        (C6, C7, "micro", add(MO, (6, -30, 12)), add(MO, (3, -26, 15)), add(MO, (0, 0, 3)), add(MO, (0, 0, 7)), 30),
        (C7, C8, "lab", add(LO, (1.5, -30, 11.5)), add(LO, (1.0, -24, 8.0)), add(LO, (0, 0, 9.5)),
         add(LO, (0, 0, 6.5)), 35),
        (C8, C9, "lab", add(LO, (1.2, -30, 9.0)), add(LO, (0.6, -40, 19)), add(LO, (0, 0, 9.0)),
         add(LO, (0, 0, 23)), 30),
        (C9, C10, "yard", add(YO, (-10, -74, 14)), add(YO, (-7, -66, 18)), add(YO, (4, 0, 52)),
         add(YO, (4, 0, 60)), 18),
        (C10, DUR, "yard", None, None, None, None, 24),
    ]


SHOTS = _shots()
S_WIDE, S_WHY, S_SQZ, S_SEED, S_PITSA, S_PITSB, S_BUB, S_SINK, S_PUSH, S_DIET = range(1, 11)
SET_OF = [s[2] for s in SHOTS]
LOOP_I = len(SHOTS) - 1


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if t < s[1]:
            return i
    return len(SHOTS) - 1


# ---------------------------------------------------------------- the geyser (shared by picture and sound)
def geyser_strength(te):
    """1 while the bottle is full of foam, then the jet weakens as the bottle empties."""
    if te < 0:
        return 0.0
    return 1.0 if te < 4.4 else max(0.15, math.exp(-(te - 4.4) / 2.0))


def jet_top(te, H):
    """Height of the jet's top (inches) for a geyser that peaks at H."""
    if te <= 0:
        return G.BOT_TOP
    v = math.sqrt(2 * G.G_IN * (H - G.BOT_TOP))
    tp = v / G.G_IN
    front = G.BOT_TOP + (v * te - 0.5 * G.G_IN * te * te if te < tp else H - G.BOT_TOP)
    return G.BOT_TOP + (front - G.BOT_TOP) * (0.35 + 0.65 * geyser_strength(te)) if te > tp else front


def yard_clock(t):
    """(hero te or None, comparison te or None)."""
    i = shot_index(t)
    if i in (0, S_WIDE):
        return t + RE0, None
    if i == LOOP_I:
        return t - DUR + RE0, None
    if i == S_DIET:
        return None, t - T_DIET_GO
    return None, None


def mentos_drop(te, k):
    """Height of the k-th Mentos (bottom of the stack first) in the loop shot, or None once inside the foam."""
    a = te - T_LOOP_DROP - 0.035 * k
    z0 = G.BOT_TOP + 30.0 + k * (G.MENTOS_H + 0.02)
    if a < 0:
        return z0
    return z0 - 0.5 * G.G_IN * a * a


# ---------------------------------------------------------------- cameras
CAM0_LOC = np.array(YO) + np.array([11.0, -24.0, 5.0])
CAM0_VEL = np.array([1.2, -2.6, 2.2])
CAM0_TGT = np.array(YO) + np.array([0.0, 0.0, 33.0])


def cam0(t):
    """Hook camera; linear in t, so it is smooth when evaluated at negative time in the loop shot."""
    return tuple(CAM0_LOC + CAM0_VEL * t), tuple(CAM0_TGT + np.array([0.0, 0.0, 9.0]) * t), 20.0


LOOPW_LOC = np.array(YO) + np.array([5.0, -23.0, 15.5])
LOOPW_TGT = np.array(YO) + np.array([0.0, 0.0, 15.0])


def camera(t):
    i = shot_index(t)
    t0, t1, _s, p0, p1, a0, a1, lens = SHOTS[i]
    if i == 0:
        return cam0(t)
    if i == LOOP_I:
        tn = t - DUR
        loc, tgt, ln = cam0(tn)
        w = smoother((tn - (t0 - DUR) - 0.05) / (-(t0 - DUR) - 0.40))   # wide on the bottle -> hook camera
        return (tuple(lerp(a, b, w) for a, b in zip(LOOPW_LOC, loc)),
                tuple(lerp(a, b, w) for a, b in zip(LOOPW_TGT, tgt)), lerp(28.0, ln, w))
    x = clamp((t - t0) / (t1 - t0))
    u = smoother(x) * 0.6 + 0.4 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lens


def shake(t):
    i = shot_index(t)
    te, _ = yard_clock(t)
    if i in (0, LOOP_I) and te is not None and te > 0:
        return 0.35 * math.exp(-te / 0.35)
    if i == S_PUSH:
        a = t - T_JET_LAB
        return 0.12 * math.exp(-a / 0.3) if a > 0 else 0.0
    return 0.0


if __name__ == "__main__":
    print("NFRAMES", NFRAMES, "DUR", round(DUR, 2))
    for k, s in enumerate(SHOTS):
        print(k, s[2], round(s[0], 2), round(s[1], 2), int(math.ceil(s[0] * FPS - 1e-9)))
