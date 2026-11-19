"""Shot timeline for the tardigrade video, derived from the real narration timing (vo/timing.json)."""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}

FPS = 30
DUR = round(L["still"][1] + 0.08, 2)          # loop restarts right after the last word (user feedback)
NFRAMES = int(DUR * FPS)

# set origins (each world lives far from the others)
SPACE = (0.0, 0.0, 0.0)
RULER = (500.0, 0.0, 0.0)
MOSS = (1000.0, 0.0, 0.0)
DROP = (1500.0, 0.0, 0.0)
MOON = (2000.0, 0.0, 0.0)
MOON_SPHERE = (-260.0, 900.0, 160.0)        # the Moon far away (only big in the "crazy" push-in)
EARTH_C = (0.0, 420.0, -260.0)              # Earth far below/behind: a curved limb low in frame


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


# ---------------------------------------------------------------- hero states
def tun_moss(t):
    """0 = active, 1 = tun. Dries during 'dries', wakes during 'wakes'."""
    d0, d1 = L["dries"]
    w0, w1 = L["wakes"]
    if t < w0:
        return smoother((t - d0 - 0.4) / (d1 - d0 - 0.4))
    return 1 - smoother((t - w0 - 0.5) / (w1 - w0 - 0.3))


def drop_fall(t):
    """Water drop falling onto the tun at the start of 'wakes': z offset above the bear (0 = landed)."""
    w0 = L["wakes"][0]
    u = clamp((t - (w0 - 0.15)) / 0.55)
    return 5.0 * (1 - u * u)


def drop_spread(t):
    """After landing the drop spreads into a thin film (0..1)."""
    w0 = L["wakes"][0]
    return smoother((t - (w0 + 0.4)) / 0.6)


def babies(t):
    """0..1 hatch progress of the babies."""
    b0, b1 = L["babies"]
    return smoother((t - b0 - 0.6) / (b1 - b0))


def plume(t):
    """Lunar dust plume progress 0..1 (crash at the start of the 'moon' line)."""
    m0 = L["moon"][0] + 0.9
    return clamp((t - m0) / 2.4)


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    sp = lambda x, y, z: add(SPACE, (x, y, z))
    ru = lambda x, y, z: add(RULER, (x, y, z))
    mo = lambda x, y, z: add(MOSS, (x, y, z))
    dr = lambda x, y, z: add(DROP, (x, y, z))
    mn = lambda x, y, z: add(MOON, (x, y, z))
    hero0, hero1 = sp(1.2, -6.2, 1.1), sp(1.6, -5.2, 0.9)
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, roll0, roll1, set
        (0.0, l["hook"][0] + 1.9, hero0, hero1, sp(0, 0, 0), sp(0, 0, 0), 55, 55, 8, "hero", 0, 0, "space"),
        (l["hook"][0] + 1.9, l["size"][0] - 0.1, sp(-2.6, -2.4, 0.4), sp(-2.0, -2.0, 0.55), sp(0, 0, 0), sp(0, 0, 0), 65, 65, 8, "hero", 0, 0, "space"),
        (l["size"][0] - 0.1, l["dries"][0] - 0.1, ru(1.2, -6.4, 3.6), ru(1.0, -5.6, 3.1), ru(0.2, -0.6, 0.0), ru(0.5, -0.6, 0.0), 32, 32, 8, "hero", 0, 0, "ruler"),
        (l["dries"][0] - 0.1, l["wakes"][0] - 0.25, mo(2.6, -3.2, 1.6), mo(2.1, -2.6, 1.4), mo(0, 0, 0.45), mo(0, 0, 0.45), 55, 55, 3.2, "hero", 0, 0, "moss"),
        (l["wakes"][0] - 0.25, l["babies"][0] - 0.1, mo(-3.6, -4.2, 1.9), mo(-3.2, -3.7, 1.7), mo(0, 0, 0.6), mo(0, 0, 0.5), 40, 40, 4.0, "hero", 0, 0, "moss"),
        (l["babies"][0] - 0.1, l["crazy"][0] - 0.05, dr(-0.1, -5.6, 1.9), dr(0.0, -4.9, 1.65), dr(0.0, -0.1, -0.1), dr(0.0, -0.1, -0.1), 30, 30, 5.6, "hero", 0, 0, "drop"),
        (l["crazy"][0] - 0.05, l["moon"][0] - 0.05, sp(2.0, -6.0, 1.0), sp(1.0, -4.0, 1.4), sp(-260, 900, 160), sp(-260, 900, 160), 60, 120, 16, None, 0, -5, "space"),
        (l["moon"][0] - 0.05, l["moon"][0] + 1.9, mn(-11.0, 4.0, 4.5), mn(-9.0, 7.0, 4.0), mn(0, 25, 3.5), mn(0, 25, 3.0), 30, 30, 16, None, 0, 0, "moon"),
        (l["moon"][0] + 1.9, l["still"][0] - 0.05, mn(4.6, 18.6, 0.9), mn(4.0, 19.3, 0.85), mn(1.4, 23.0, 0.25), mn(1.2, 23.4, 0.35), 32, 32, 4.0, "crash", 0, 0, "moon"),
        (l["still"][0] - 0.05, DUR + 0.1, mn(1.8, -4.6, 0.55), mn(1.4, -3.9, 0.7), mn(0, 0, 0.6), mn(0, 0, 1.4), 45, 45, 6, "hero", 0, 0, "moon"),
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
    p = tuple(a + b for a, b in zip(p, drift(t, 0.01)))
    return p, lerpv(a0, a1, u), lerp(l0, l1, u), fstop, focus, lerp(r0, r1, u)


def hero_pos(t):
    """Where the hero bear is in the current set (camera focus)."""
    st = shot_set(t)
    if st == "space":
        return SPACE
    if st == "ruler":
        return add(RULER, (lerp(-0.4, 0.9, (t - SHOTS[2][0]) / (SHOTS[2][1] - SHOTS[2][0])), 0, 0.3))
    if st == "moss":
        return add(MOSS, (0, 0, 0.45))
    if st == "drop":
        return add(DROP, (0.3, 0, 0.1))
    return add(MOON, (0, 0, 0.35))
