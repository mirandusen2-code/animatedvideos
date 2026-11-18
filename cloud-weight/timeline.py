"""Shot timeline for the cloud video, derived from the real narration timing (vo/timing.json)."""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}

FPS = 30
DUR = round(L["feather"][1] + 0.5, 2)
NFRAMES = int(DUR * FPS)


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


# ---------------------------------------------------------------- world layout
CLOUD = (0.0, 0.0, 30.0)          # centre of the hero cloud (cloud ~16 units wide, ~9 tall)
CLOUD_TOP = 34.5
HOOK = (0.0, 0.0, CLOUD_TOP + 1.0)
DIAL = (0.0, 0.0, CLOUD_TOP + 6.5)  # crane-scale dial centre (dial faces -y)
DROPS = (600.0, 0.0, 0.0)         # macro set: inside the cloud
HERD = (0.0, 0.0, 0.0)            # elephants stand on the ground under the cloud


def needle(t):
    """Dial needle angle (rad, clockwise from 12 o'clock): swings to 'full' with an overshoot."""
    x = clamp((t - 0.25) / 1.6)
    over = 1 + 0.08 * math.sin(x * math.pi * 3) * (1 - x)
    return math.radians(300) * ease_out(x) * over


def cube_draw(t):
    """0..1: the glass air-cube drawing itself around the cloud."""
    a0 = L["air"][0] - 0.1
    return smoother((t - a0) / 1.4)


def feather_pos(t):
    """Feather drifting down past the cloud in the last line (sways side to side)."""
    t0 = L["feather"][0] - 0.3
    u = clamp((t - t0) / (DUR - t0))
    z = lerp(CLOUD[2] + 4.0, CLOUD[2] - 7.0, u)
    x = 4.5 + 1.6 * math.sin(u * 7.0)
    return (x, -9.0 + 2.0 * u, z), (0.5 * math.sin(u * 7.0 + 1.2), 0.25 * math.cos(u * 6), u * 2.0)


# ---------------------------------------------------------------- shots
def _shots():
    l = L
    c = CLOUD
    pt = lambda x, y, z: (c[0] + x, c[1] + y, c[2] + z)
    dr = lambda x, y, z: (DROPS[0] + x, DROPS[1] + y, DROPS[2] + z)
    hero0, hero1 = pt(9.0, -40.0, -12.0), pt(7.5, -34.0, -10.5)
    hero_t = pt(0.0, 0.0, 3.0)
    dial_t = DIAL
    k1 = l["hook"][0] + 2.1                       # cut to the dial as the number lands
    k2 = l["elephants"][0] + 1.3
    k3 = l["droplets"][0] + 0.1
    k4 = l["light"][0] + 0.1
    k5 = l["air"][0] + 1.6
    return [
        # t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, roll0, roll1, set
        (0.0, k1, hero0, hero1, hero_t, hero_t, 24, 24, 11, None, 0, 0, "sky"),
        (k1, l["pounds"][1] + 0.15, (DIAL[0] + 2.2, DIAL[1] - 9.0, DIAL[2] - 0.6), (DIAL[0] + 1.6, DIAL[1] - 7.6, DIAL[2] - 0.4),
         dial_t, dial_t, 50, 50, 4, "dial", 0, 0, "sky"),
        (l["pounds"][1] + 0.15, k2, (-26.0, -46.0, 2.2), (-22.0, -40.0, 2.6), pt(0, 0, -8), pt(0, 0, -6), 20, 20, 8, None, 0, 0, "sky"),
        (k2, l["why"][0] - 0.1, (14.0, -30.0, 52.0), (11.0, -24.0, 48.0), (0.0, 0.0, 2.0), (0.0, 0.0, 6.0), 26, 26, 11, None, 0, 0, "sky"),
        (l["why"][0] - 0.1, k3, pt(3.0, -36.0, 1.0), pt(0.6, -9.5, 0.5), pt(0, 0, 0), pt(0, 0, 0), 30, 30, 11, None, 0, 6, "sky"),
        (k3, k4, dr(0.0, -2.6, 0.2), dr(0.25, -2.1, 0.3), dr(0, 0, 0.1), dr(0.1, 0, 0.2), 60, 60, 1.6, "drop", 0, 0, "drops"),
        (k4, l["crazy"][0] - 0.05, dr(-2.2, -1.2, -0.6), dr(-1.9, -1.0, -0.3), dr(0, 0, 0.5), dr(0, 0, 0.8), 45, 45, 2.0, "drop", 0, 0, "drops"),
        (l["crazy"][0] - 0.05, l["air"][0] - 0.1, pt(-30.0, -70.0, 6.0), pt(-16.0, -42.0, 4.0), pt(0, 0, 1), pt(0, 0, 1), 28, 28, 11, None, 0, -4, "sky"),
        (l["air"][0] - 0.1, k5, pt(26.0, -42.0, 14.0), pt(22.0, -36.0, 12.0), pt(0, 0, 1), pt(0, 0, 1), 24, 24, 11, None, 0, 0, "sky"),
        (k5, l["feather"][0] - 0.1, pt(-24.0, -30.0, -8.0), pt(-20.0, -26.0, -6.0), pt(0, 0, 2), pt(0, 0, 2), 22, 22, 11, None, 0, 0, "sky"),
        (l["feather"][0] - 0.1, DUR + 0.1, pt(11.0, -45.0, -13.0), hero0, hero_t, hero_t, 24, 24, 11, None, 0, 0, "sky"),
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


SHAKES = [(0.25, 0.4), (L["crazy"][0] - 0.05, 0.7)]


def camera(t):
    t0, t1, p0, p1, a0, a1, l0, l1, fstop, focus, r0, r1, _set = SHOTS[shot_index(t)]
    u = smoother((t - t0) / (t1 - t0)) * 0.85 + 0.15 * clamp((t - t0) / (t1 - t0))
    p = lerpv(p0, p1, u)
    amp = 0.003 if focus == "drop" else 0.05
    p = tuple(a + b for a, b in zip(p, drift(t, amp)))
    for ts, s in SHAKES:
        if ts <= t < ts + 7 / FPS:
            k = 1 - (t - ts) / (7 / FPS)
            sc = s * k * (0.02 if focus == "drop" else 0.35)
            p = (p[0] + sc * math.sin(t * 173), p[1] + sc * math.sin(t * 131), p[2] + sc * math.sin(t * 157))
    return p, lerpv(a0, a1, u), lerp(l0, l1, u), fstop, focus, lerp(r0, r1, u)
