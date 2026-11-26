"""Shot timeline for "Why Airplane Windows Are Round", derived from the narration timing (1 unit = 1 ft).

The tear in the rip set runs on its own slow-motion clock (rip_clock): the loop shot runs at negative time (the crack
races from the window corner) and flows straight into frame 0 (the skin blowing out). Picture and sound read the same
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
T_WINDOWS, T_SQUARE, T_PLANES, T_RIPPED, T_APART, T_SKY = (W("hook", w) for w in
                                                          ("windows", "square", "planes", "ripped", "apart", "sky"))
T_WHY, T_EVERY, T_CABIN, T_PUMPED, T_BALLOON = (W("why", w) for w in ("why", "every", "cabin", "pumped", "balloon"))
T_SHARP, T_CORNER, T_PUSH, T_PILES, T_ONE, T_TINY, T_SPOT = (W("corner", w) for w in
                                                             ("sharp", "corner", "push", "piles", "one", "tiny",
                                                              "spot"))
T_FLIGHT, T_CRACK, T_GROWS, T_THERE = W("crack", "flight"), W("crack", "crack"), W("crack", "grows"), \
    W("crack", "there")
T_1954, T_TWO, T_FIRST, T_JETL, T_BROKE, T_MIDAIR = (W("comet", w) for w in
                                                     ("1954", "two", "first", "jetliners", "broke", "mid"))
T_ENGS, T_SANK, T_TANK, T_TPUMPED, T_AGAIN, T_AGAIN2 = W("tank", "engineers"), W("tank", "sank"), W("tank", "tank"), \
    W("tank", "pumped"), W("tank", "again"), W("tank", "again", 1)
T_3000, T_FLIGHTS, T_SPLITW, T_OPEN, T_WCORNER = W("burst", "3000"), W("burst", "flights"), W("burst", "split"), \
    W("burst", "open"), W("burst", "corner")
T_ROUND, T_SPREADS, T_AROUND, T_NO, T_WEAK = W("round", "round"), W("round", "spreads"), W("round", "around"), \
    W("round", "no"), W("round", "weak")
T_SO, T_FLY, T_REMEMBER = W("loop", "so"), W("loop", "fly"), W("loop", "remember")

# ---------------------------------------------------------------- shot cut times
C1 = T_PLANES[0] - 0.02                      # rip close-up -> the whole jet breaking apart
C2 = L["hook"][1] + 0.12                     # -> cabin cross-section (why)
C3 = L["why"][1] + 0.12                      # -> stress map (corner)
C4 = L["corner"][1] + 0.12                   # -> crack close-up
C5 = L["crack"][1] + 0.12                    # -> the Comet, 1954
C6 = L["comet"][1] + 0.12                    # -> water tank, wide
C7 = L["tank"][1] + 0.12                     # -> the split, close
C8 = L["burst"][1] + 0.12                    # -> round window (map)
C9 = L["round"][1] + 0.12                    # -> loop (rip)

RE0 = 0.2                                    # frame 0 shows the tear 0.2 s (slow-motion) after it starts
T_RUPT1 = T_RIPPED[0] + 0.03                 # the jet breaks apart in S1
T_RUPT2 = T_BROKE[0] - 0.04                  # ... and in S5
T_INFL = T_PUMPED[0] - 0.08                  # cabin starts to swell
T_HEAT = T_PUSH[0] - 0.1                     # push lines start to pile up (heat grows)
T_CR0 = T_CRACK[0] - 0.05                    # crack starts growing in S4
T_CYC0 = T_TPUMPED[0] - 0.05                 # pressure cycling starts
T_SPLIT = T_SPLITW[0] - 0.04                 # the tank airframe splits
T_MORPH = T_ROUND[0] - 0.05                  # square -> round
N_CYC = 3060                                 # pressurized "flights" on the test airframe when it failed


def _shots():
    P = tuple(G.rip_surf(*G.W0_CORNER))
    CM = tuple(G.COMET_O)
    CO = tuple(G.CUT_O)
    MO = tuple(G.MAP_O)
    MC = (G.MAP_CORNER[0], 0.0, G.MAP_CORNER[1])
    TO = tuple(G.TANK_O)
    SP = tuple(G.jet_surf(G.JET_WIN_S[3] - 0.62, -math.radians(78) + 0.62 / G.JET_R, G.TANK_O))
    return [
        # t0, t1, set, loc0, loc1, tgt0, tgt1, lens
        (0.0, C1, "rip", None, None, None, None, 28),
        (C1, C2, "comet", add(CM, (-48, 30, -16)), add(CM, (-42, 22, -12)), add(CM, (0, -36, 1)),
         add(CM, (0, -40, -1)), 26),
        (C2, C3, "cut", add(CO, (0.6, -21, 0.9)), add(CO, (0.3, -16.5, 0.6)), add(CO, (0, 4, 0.1)), add(CO, (0, 4, 0.1)),
         32),
        (C3, C4, "map", add(MO, (0.3, -15.5, 0.2)), add(MO, MC, (0.5, -6.0, 0.4)), add(MO, (0, 0, 0.1)),
         add(MO, MC, (0.2, 0, 0.15)), 30),
        (C4, C5, "map", add(MO, MC, (1.6, -4.4, 1.5)), add(MO, MC, (2.2, -4.6, 2.0)), add(MO, MC, (0.5, 0, 0.5)),
         add(MO, MC, (1.2, 0, 1.2)), 34),
        (C5, C6, "comet", add(CM, (-62, 34, 24)), add(CM, (-52, 18, 17)), add(CM, (0, -36, -3)),
         add(CM, (0, -42, -5)), 28),
        (C6, C7, "tank", add(TO, (-10.5, 5.5, 3.0)), add(TO, (-9.5, 1.5, 2.2)), add(TO, (-1, -30, -1.0)), add(TO, (-1, -33, -1.0)),
         24),
        (C7, C8, "tank", add(SP, (-5.2, 3.4, 1.2)), add(SP, (-4.0, 2.6, 0.8)), add(SP, (0, -0.3, 0)),
         add(SP, (0, -0.4, 0)), 30),
        (C8, C9, "map", add(MO, (0.5, -12.5, 0.3)), add(MO, (0.3, -10.5, 0.2)), add(MO, (0, 0, 0.1)),
         add(MO, (0, 0, 0.1)), 30),
        (C9, DUR, "rip", None, None, None, None, 28),
    ]


SHOTS = _shots()
SET_OF = [s[2] for s in SHOTS]
LOOP_I = len(SHOTS) - 1


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if t < s[1]:
            return i
    return len(SHOTS) - 1


# ---------------------------------------------------------------- clocks / states
def rip_clock(t):
    """Slow-motion time since the skin tore (frame 0 = RE0); negative in the loop shot."""
    i = shot_index(t)
    if i == 0:
        return t + RE0
    if i == LOOP_I:
        return t - DUR + RE0
    return None


def rip_state(t):
    """(te, window exponent, crack length before the tear)."""
    te = rip_clock(t)
    if shot_index(t) == LOOP_I:
        n = lerp(G.N_ROUND, G.N_SQUARE, smoother((t - (T_REMEMBER[0] - 0.55)) / 0.6))
        crack = 1.5 * smoother((te + 0.85) / 0.85) ** 1.4
        return te, n, crack
    return te, G.N_SQUARE, 0.0


def comet_clock(t):
    """(time since the rupture, running time)."""
    i = shot_index(t)
    if i == 1:
        return t - T_RUPT1, t
    if i == 5:
        return t - T_RUPT2, t
    return -1.0, t


def cut_state(t):
    p = smoother((t - T_INFL) / 1.1)
    return p, t


def map_state(t):
    """(n, gain, flow time, push visibility, crack length, pulse)."""
    i = shot_index(t)
    if i == 3:
        g = 0.12 + 0.88 * smoother((t - T_HEAT) / 1.3)
        pulse = math.sin(2 * math.pi * 1.6 * t) * smoother((t - T_PILES[0]) / 0.4)
        return G.N_SQUARE, g, t, 1.0, 0.0, pulse
    if i == 4:
        crack = 2.4 * smoother((t - T_CR0) / 1.5) ** 0.85
        pulse = math.sin(2 * math.pi * 1.6 * t)
        return G.N_SQUARE, 1.0, t, 0.85, crack, pulse
    if i == 8:
        m = smoother((t - T_MORPH) / 0.8)
        n = lerp(G.N_SQUARE, G.N_ROUND, m)
        return n, 1.0, t, 1.0, 0.0, 0.0
    return G.N_SQUARE, 1.0, t, 1.0, 0.0, 0.0


def cycles_at(t):
    """Pressure cycles done (the counter) and the cycle phase, for the tank shots."""
    a = clamp((t - T_CYC0) / (T_SPLIT - T_CYC0))
    n = N_CYC * a ** 2.2
    # the visible pulses: start slow (one per ~0.7 s) then speed up
    tt = max(0.0, t - T_CYC0)
    ph = 1.4 * tt + 0.55 * tt * tt
    return n, ph


def tank_state(t):
    n, ph = cycles_at(t)
    press = 0.0 if t < T_CYC0 else 0.5 - 0.5 * math.cos(2 * math.pi * ph)
    if t >= T_SPLIT:
        press = max(0.0, 1.0 - (t - T_SPLIT) * 1.5)
    return press, t - T_SPLIT


# ---------------------------------------------------------------- cameras
P_C = np.array(G.rip_surf(*G.W0_CORNER))
CAM0_LOC = P_C + np.array([-3.9, -3.6, 0.7])
CAM0_VEL = np.array([-0.3, -0.45, 0.1])
CAM0_TGT = P_C + np.array([0.0, 0.25, -0.45])
SIDE_LOC = np.array(G.rip_surf(-9.0, 0.3)) + np.array([-8.0, 0.0, 1.6])


def cam0(t):
    """Hook camera; linear in t, so it is smooth when evaluated at negative time in the loop shot."""
    return tuple(CAM0_LOC + CAM0_VEL * t), tuple(CAM0_TGT + np.array([0.0, 0.12, -0.03]) * t), 28.0


def camera(t):
    i = shot_index(t)
    t0, t1, _s, p0, p1, a0, a1, lens = SHOTS[i]
    if i == 0:
        return cam0(t)
    if i == LOOP_I:
        tn = t - DUR
        loc, tgt, ln = cam0(tn)
        w = smoother((tn + 2.0) / 1.55)            # glide along the window row -> hook camera (pure by tn = -0.45)
        side_l = SIDE_LOC + np.array([0.0, 3.4, 0.0]) * (tn + 2.45)
        side_t = side_l + np.array([3.2, 5.5, -0.6])
        return (tuple(lerp(a, b, w) for a, b in zip(side_l, loc)),
                tuple(lerp(a, b, w) for a, b in zip(side_t, tgt)), lerp(30.0, ln, w))
    x = clamp((t - t0) / (t1 - t0))
    u = smoother(x) * 0.6 + 0.4 * x
    return lerpv(p0, p1, u), lerpv(a0, a1, u), lens


def shake(t):
    i = shot_index(t)
    te = rip_clock(t)
    if i == 0 and te is not None:
        return 0.06 * math.exp(-te / 0.35)
    if i == 7:
        a = t - T_SPLIT
        return 0.04 * math.exp(-a / 0.3) if a > 0 else 0.0
    return 0.0


if __name__ == "__main__":
    print("NFRAMES", NFRAMES, "DUR", round(DUR, 2))
    for k, s in enumerate(SHOTS):
        print(k, s[2], round(s[0], 2), round(s[1], 2), int(math.ceil(s[0] * FPS - 1e-9)))
    for f in list(range(NFRAMES - 75, NFRAMES, 5)) + [NFRAMES - 1]:
        l, g, ln = camera(f / FPS)
        print(f, [round(c, 2) for c in l], round(ln, 1), rip_state(f / FPS))
    print(0, [round(c, 2) for c in camera(0)[0]])
