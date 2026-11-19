"""Shot timeline for the mantis shrimp video, derived from the real narration timing (vo/timing.json)."""
import json
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}
WORDS = TIMING["words"]

FPS = 30
DUR = round(L["loop"][1] + 0.08, 2)           # loop restarts right after the last word
NFRAMES = int(DUR * FPS)

# set origins (each world lives far from the others)
TANK = (0.0, 0.0, 0.0)
REEF = (500.0, 0.0, 0.0)
MACRO = (1000.0, 0.0, 0.0)


def W(line, word):
    """(start, end) of the first caption word in `line` containing `word` (case-insensitive)."""
    a, b = L[line]
    for s, e, w, *_ in WORDS:
        if a - 0.01 <= s <= b + 0.01 and word.lower() in re.sub(r"[^a-z0-9]", "", w.lower()):
            return s, e
    raise KeyError((line, word))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp(x)
    return x * x * x


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def add(a, b):
    return tuple(p + q for p, q in zip(a, b))


# ---------------------------------------------------------------- strike curves (0 = cocked, 1 = fully out)
def _strike(t, t_hit, out=0.10, hold=0.25, back=0.45):
    """Fast strike that reaches the target at t_hit, holds, then folds back."""
    if t < t_hit - out:
        return 0.0
    if t < t_hit:
        return ease_in((t - (t_hit - out)) / out) ** 0.6
    if t < t_hit + hold:
        return 1.0
    return 1.0 - smoother((t - t_hit - hold) / back)


T_PUNCH = W("hook", "punch")[0] + 0.05          # first punch on the glass
T_GLASS = W("hook", "glass")[0] + 0.02          # second punch: the crack spreads
T_SNAIL = W("snail", "smash")[0] + 0.12         # the snail shell shatters
T_POP = W("collapse", "second")[0]              # bubbles collapse: the flash
T_ONE = W("loop", "one")[0] + 0.02
T_TWO = W("loop", "two")[0] + 0.02


def strike_tank(t):
    return max(_strike(t, T_PUNCH), _strike(t, T_GLASS))


def crack(t):
    """Crack radius on the glass (0..1 of full size)."""
    return 0.22 * ease_out((t - T_PUNCH) / 0.4) + 0.78 * ease_out((t - T_GLASS) / 0.8)


def strike_slowmo(t):
    """Slow-motion swing in the 'speed' shot (side view): unfolds over most of the line."""
    a, b = L["speed"]
    return smoother((t - a - 0.2) / (b - a - 0.2)) * 0.95


def strike_blink(t):
    """Two quick strikes behind the eye close-up."""
    a, b = L["blink"]
    return max(_strike(t, a + 0.35, hold=0.12, back=0.3), _strike(t, a + 1.0, hold=0.12, back=0.3))


def strike_snail(t):
    return _strike(t, T_SNAIL, hold=0.4, back=0.6)


def shatter(t):
    """Seconds since the snail shell broke (negative = still whole)."""
    return t - T_SNAIL


def strike_loop(t):
    return max(_strike(t, T_ONE, hold=0.15, back=0.35), _strike(t, T_TWO, hold=0.15, back=0.35))


def macro_club(t):
    """Club position along the ultra slow-motion approach (0 far .. 1 at the shell)."""
    a = L["crazy"][0]
    return ease_out((t - a) / (T_POP - a)) ** 1.2


def bubbles(t):
    """Bubble growth 0..1 during 'bubbles', then they collapse to 0 at T_POP."""
    b0, b1 = L["bubbles"]
    grow = smoother((t - b0 - 0.3) / (b1 - b0 - 0.2))
    shrink = 1 - ease_in((t - (T_POP - 0.9)) / 0.9)
    return grow * shrink if t < T_POP else 0.0


def flash(t):
    """Flash intensity: a sharp spike at T_POP, a warm glow through the 'heat' line, then gone."""
    if t < T_POP - 0.03:
        return 0.0
    spike = math.exp(-(t - T_POP) / 0.18)
    h0, h1 = L["heat"]
    glow = 0.35 * smoother((t - T_POP) / 0.3) * (1 - smoother((t - h1 + 0.2) / 0.6))
    return min(1.0, spike + glow)


def ring(t):
    """Shock ring 0..1 expanding from the collapse."""
    return clamp((t - T_POP) / 0.9)


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    tk = lambda x, y, z: add(TANK, (x, y, z))
    rf = lambda x, y, z: add(REEF, (x, y, z))
    mc = lambda x, y, z: add(MACRO, (x, y, z))
    t_close = W("hook", "enough")[1] - 0.05
    t_mid = W("heat", "over")[0] - 0.05
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, roll0, roll1, set
        (0.0, t_close, tk(3.7, -1.3, 0.62), tk(3.3, -1.0, 0.58), tk(0.8, 0, 0.3), tk(0.85, 0, 0.3), 45, 45, 5.6, "hero", 0, 0, "tank"),
        (t_close, l["speed"][0] - 0.05, tk(2.9, 0.9, 0.45), tk(2.6, 0.7, 0.42), tk(1.0, 0, 0.26), tk(1.0, 0, 0.26), 38, 38, 4.0, "glass", 0, 0, "tank"),
        (l["speed"][0] - 0.05, l["blink"][0] - 0.05, rf(0.55, -2.7, 0.5), rf(0.75, -2.4, 0.46), rf(0.6, 0, 0.28), rf(0.7, 0, 0.28), 40, 40, 5.6, "club", 0, 0, "reef"),
        (l["blink"][0] - 0.05, l["snail"][0] - 0.05, rf(1.55, -0.62, 0.85), rf(1.47, -0.55, 0.82), rf(0.97, 0.0, 0.52), rf(0.97, 0.0, 0.52), 55, 55, 2.8, "eye", 0, 0, "reef"),
        (l["snail"][0] - 0.05, l["crazy"][0] - 0.05, rf(3.0, -2.2, 0.85), rf(2.6, -1.9, 0.7), rf(1.05, 0, 0.22), rf(1.15, 0, 0.2), 40, 40, 5.6, "snail", 0, 0, "reef"),
        (l["crazy"][0] - 0.05, l["bubbles"][0] - 0.05, mc(-2.0, -8.2, 1.0), mc(-1.6, -6.6, 0.6), mc(-1.7, 0, 0), mc(-1.2, 0, 0), 40, 42, 8, "club", 0, -3, "macro"),
        (l["bubbles"][0] - 0.05, l["collapse"][0] - 0.05, mc(-0.4, -5.6, 0.9), mc(-0.2, -4.6, 0.6), mc(-0.6, 0, 0), mc(-0.45, 0, 0), 50, 50, 8, "gap", 0, 0, "macro"),
        (l["collapse"][0] - 0.05, l["heat"][0] - 0.05, mc(-0.7, -3.4, -0.7), mc(-0.8, -3.0, -0.5), mc(-0.35, 0, 0), mc(-0.35, 0, 0), 45, 45, 8, "gap", 2, 0, "macro"),
        (l["heat"][0] - 0.05, t_mid, mc(-1.5, -6.5, 1.2), mc(-1.2, -7.4, 1.0), mc(-0.4, 0, 0), mc(-0.4, 0, 0), 45, 45, 8, "gap", 0, 0, "macro"),
        (t_mid, l["loop"][0] - 0.05, mc(-3.4, -2.6, 2.4), mc(-3.0, -2.2, 2.0), mc(-0.3, 0, 0), mc(-0.3, 0, 0), 35, 35, 8, "gap", 0, 0, "macro"),
        (l["loop"][0] - 0.05, DUR + 0.1, rf(3.6, -1.3, 0.65), rf(3.2, -1.1, 0.6), rf(0.7, 0, 0.3), rf(0.75, 0, 0.3), 42, 42, 5.6, "hero", 0, 0, "reef"),
    ]


SHOTS = _shots()


def shot_index(t):
    for i, s in enumerate(SHOTS):
        if s[0] <= t < s[1]:
            return i
    return len(SHOTS) - 1


def shot_set(t):
    return SHOTS[shot_index(t)][12]


def drift(t, amp):
    return (amp * math.sin(t * 0.9) + amp * 0.5 * math.sin(t * 2.3), amp * 0.6 * math.sin(t * 1.3 + 1),
            amp * math.sin(t * 1.1 + 2) + amp * 0.4 * math.sin(t * 2.9))


def camera(t):
    t0, t1, p0, p1, a0, a1, l0, l1, fstop, focus, r0, r1, _set = SHOTS[shot_index(t)]
    u = smoother((t - t0) / (t1 - t0)) * 0.85 + 0.15 * clamp((t - t0) / (t1 - t0))
    p = lerpv(p0, p1, u)
    p = tuple(a + b for a, b in zip(p, drift(t, 0.008)))
    return p, lerpv(a0, a1, u), lerp(l0, l1, u), fstop, focus, lerp(r0, r1, u)
