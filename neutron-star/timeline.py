"""Shot timeline derived from the real narration timing (vo/timing.json): picture follows the voice."""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TIMING = json.load(open(os.path.join(HERE, "vo", "timing.json")))
L = {k: tuple(v) for k, v in TIMING["lines"].items()}   # key -> (start, end)

FPS = 30
DUR = round(L["why"][1] + 0.45, 2)
NFRAMES = int(DUR * FPS)

# shot boundaries
T_MACRO = L["notsugar"][0] - 0.2          # studio wide -> macro of the cube
T_SPACE = L["dies"][0] - 0.15             # -> space: the dying star
T_COLLAPSE = L["dies"][1] - 0.35          # core collapses (end of "collapses")
T_PULSAR = L["crazy"][0] - 0.05           # -> pulsar shot (re-hook impact)
T_BACK = L["billion"][0] - 0.15           # -> back to the glowing cube
T_END = L["why"][0] - 0.1                 # -> wide: a new cube drops (loops to frame 0)
GLOW_ON = (L["neutron"][0] + 0.3, L["neutron"][1] + 0.2)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp(x)
    return x ** 3


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def shot(t):
    if "SHOTS" in globals():
        i = shot_index(t)
        if i == 6:
            return "squeeze"            # the Sun squeezed into a tiny ball
        if i in (7, 8):
            return "city"               # neutron star over a city at night
    if t < T_MACRO:
        return "studio"
    if t < T_SPACE:
        return "macro"
    if t < T_PULSAR:
        return "star"
    if t < T_BACK:
        return "pulsar"
    if t < T_END:
        return "macro2"
    return "end"


# ---------------------------------------------------------------- balance scale
TILT_PEOPLE = 0.16      # people side down (before the cube lands)
TILT_CUBE = -0.24       # cube side down


def scale_tilt(t):
    """Beam angle (rad). Positive = right (people) pan down. At t=0 the cube has just landed:
    the beam slams to the cube side with a damped bounce. In the end shot it waits on the people side."""
    if t >= T_END:
        return TILT_PEOPLE
    return TILT_CUBE + (TILT_PEOPLE - TILT_CUBE) * math.exp(-t * 7.5) * math.cos(t * 9.0)


# scale geometry (shared with the scene)
PIVOT = (0.0, 0.0, 1.7)
ARM = 1.05
HANG = 0.9
CUBE = 0.11


def pan_pos(side, tilt):
    """Centre of the pan bottom. side -1 = cube (left), +1 = people (right)."""
    x = side * ARM * math.cos(tilt)
    z = PIVOT[2] - side * ARM * math.sin(tilt) - HANG
    return (x, 0.0, z)


def cube_drop(t):
    """Height of the cube above its pan in the end shot (falls in, lands exactly at DUR)."""
    if t < T_END + 0.3:
        return 1.6
    u = clamp((t - (T_END + 0.3)) / (DUR - (T_END + 0.3)))
    return 1.6 * (1 - u * u)


def cube_glow(t):
    if t < T_SPACE:
        return ease((t - GLOW_ON[0]) / (GLOW_ON[1] - GLOW_ON[0]))
    if t < T_END:
        return 1.0
    return 0.0


# ---------------------------------------------------------------- space
def star_scale(t):
    """Red giant radius factor: shudders, then collapses in ~0.3 s."""
    if t < T_COLLAPSE:
        shud = clamp((t - T_SPACE - 1.0) / 2.0)
        return 1.0 + 0.012 * shud * math.sin(t * 47) + 0.008 * shud * math.sin(t * 31)
    return max(0.0, 1.0 - ease_in((t - T_COLLAPSE) / 0.3))


def nova(t):
    """Supernova progress 0..1 after collapse (0 before)."""
    return clamp((t - T_COLLAPSE - 0.28) / 3.4)


def ns_visible(t):
    return clamp((t - T_COLLAPSE - 0.25) / 0.25)


def pulsar_spin(t):
    """Accumulated rotation angle (rad): accelerates during 'spin ... every second'."""
    t0 = T_PULSAR
    a, b = 0.3, 1.2                                   # rev/s start / end (slow enough to stay smooth, no strobing)
    t1, t2 = L["spin"][0], L["second"][1]
    ang = 0.0
    # integrate angular speed numerically (cheap: ~100 steps)
    n = 120
    dt = max(0.0, t - t0) / n
    for i in range(n):
        tt = t0 + (i + 0.5) * dt
        rev = lerp(a, b, ease((tt - t1) / (t2 - t1)))
        ang += 2 * math.pi * rev * dt
    return ang


# ---------------------------------------------------------------- cameras
def smoother(x):
    x = clamp(x)
    return x * x * x * (x * (6 * x - 15) + 10)


def drift(t, amp=0.004):
    return (amp * math.sin(t * 0.9) + amp * 0.5 * math.sin(t * 2.3),
            amp * 0.6 * math.sin(t * 1.3 + 1),
            amp * math.sin(t * 1.1 + 2) + amp * 0.4 * math.sin(t * 2.9))


STAR = (1000.0, 0.0, 0.0)
SUN = (2000.0, 0.0, 0.0)
CITY = (3000.0, 0.0, 0.0)
NS_CITY = (CITY[0], CITY[1], CITY[2] + 24.0)      # neutron star hovering over the city (as wide as the city)


def squeeze(t):
    """0 -> 1 progress of the Sun being squeezed (shot 6)."""
    t0, t1 = SHOTS[6][0], SHOTS[6][1]
    return smoother((t - t0 - 0.2) / (t1 - t0 - 0.5))
_CB = None   # cube position (set below)


def orbit(dist, ang, h):
    return (STAR[0] + dist * math.sin(ang), STAR[1] - dist * math.cos(ang), STAR[2] + h)


def _shots():
    """Shot list: (t0, t1, loc0, loc1, target0, target1, lens0, lens1, fstop, focus, roll0, roll1).
    focus: 'cube', 'pile' or None (= target). Max ~3 s per shot, a new angle every cut."""
    c = CUBE_POS
    pile = (pan_pos(1, TILT_CUBE)[0], 0.0, pan_pos(1, TILT_CUBE)[2] + 0.12)
    cpos = lambda dx, dy, dz: (c[0] + dx, c[1] + dy, c[2] + dz)
    sun = lambda d, a, h: (SUN[0] + d * math.sin(a), SUN[1] - d * math.cos(a), SUN[2] + h)
    city = lambda x, y, z: (CITY[0] + x, CITY[1] + y, CITY[2] + z)
    hero0, hero1 = (2.2, -2.6, 1.4), (2.1, -2.47, 1.38)
    hero_t = (0.3, 0.0, 0.9)
    l = L
    k1 = l["hook"][0] + 2.35                      # cut to the pile on "every human"
    k2 = (l["neutron"][0] - 0.05)                 # new angle as it starts glowing
    k3 = T_COLLAPSE - 0.12
    k4 = T_COLLAPSE + 1.7
    k5 = l["squeeze"][0] + 3.6
    k6 = l["city"][0] - 0.1
    k7 = l["spin"][0] - 0.05
    k8 = l["second"][0] - 0.25
    k9 = l["billion"][0] + 2.3
    return [
        (0.0, k1, hero0, hero1, hero_t, hero_t, 26, 26, 5.6, None, 0, 0),
        (k1, T_MACRO, (1.75, -0.95, 1.62), (1.55, -0.78, 1.55), pile, pile, 40, 40, 2.8, "pile", 0, 0),
        (T_MACRO, k2, cpos(0.26, -0.56, 0.05), cpos(0.2, -0.45, 0.05), c, c, 60, 60, 2.2, "cube", 0, 0),
        (k2, T_SPACE, cpos(-0.17, -0.36, 0.33), cpos(-0.11, -0.28, 0.26), c, c, 50, 50, 2.4, "cube", 0, 4),
        (T_SPACE, k3, orbit(27, -0.3, 2), orbit(23, -0.2, 2), STAR, STAR, 35, 35, 16, None, 0, 0),
        (k3, k4, orbit(16, 0.45, -2), orbit(12.5, 0.5, -1.5), STAR, STAR, 35, 35, 16, None, 3, -2),
        (k4, k5, sun(30, 0.3, 4), sun(4.2, 0.6, 0.6), SUN, SUN, 32, 32, 16, None, 0, 3),
        (k5, k6, city(23, -31, 4.5), city(17, -23.5, 5.0), city(0, 0, 14), city(0, 0, 14.5), 28, 28, 16, None, 0, 0),
        (k6, T_PULSAR, city(1.6, -4.6, 0.25), city(1.25, -3.9, 0.35), NS_CITY, NS_CITY, 16, 16, 16, None, 0, -3),
        (T_PULSAR, k7, orbit(15, 0.9, 3), orbit(7.5, 0.95, 1.6), STAR, STAR, 32, 32, 16, None, 0, -4),
        (k7, k8, orbit(11, 2.3, 0.6), orbit(10, 2.45, 0.6), STAR, STAR, 30, 30, 16, None, 0, 0),
        (k8, T_BACK, orbit(4.5, 4.0, 11), orbit(4.0, 4.2, 10), STAR, STAR, 30, 30, 16, None, 0, 0),
        (T_BACK, k9, cpos(0.02, -0.62, 0.13), cpos(0.05, -0.5, 0.1), c, c, 60, 60, 2.2, "cube", 0, 0),
        (k9, T_END, cpos(-0.15, -0.65, 0.22), (1.9, -2.9, 1.42), c, hero_t, 50, 26, 4.0, "cube", 0, 0),
        (T_END, DUR + 0.1, (2.3, -2.72, 1.42), hero0, hero_t, hero_t, 26, 26, 5.6, None, 0, 0),
    ]


SHAKES = []   # (time, strength) filled below


def shot_index(t):
    for i, sh in enumerate(SHOTS):
        if sh[0] <= t < sh[1]:
            return i
    return len(SHOTS) - 1


def camera(t):
    """(location, target, lens_mm, fstop, focus_kind, roll_deg)"""
    t0, t1, p0, p1, a0, a1, l0, l1, fstop, focus, r0, r1 = SHOTS[shot_index(t)]
    u = smoother((t - t0) / (t1 - t0)) * 0.85 + 0.15 * clamp((t - t0) / (t1 - t0))   # eased creep
    p = lerpv(p0, p1, u)
    amp = 0.004 if focus else (0.01 if p[0] < 100 else 0.06)
    p = tuple(a + b for a, b in zip(p, drift(t, amp)))
    for ts, strength in SHAKES:                       # 7-frame impact shake
        if ts <= t < ts + 7 / FPS:
            k = 1 - (t - ts) / (7 / FPS)
            sc = strength * k * (0.02 if p[0] < 100 else 0.35)
            p = (p[0] + sc * math.sin(t * 173), p[1] + sc * math.sin(t * 131), p[2] + sc * math.sin(t * 157))
    return p, lerpv(a0, a1, u), lerp(l0, l1, u), fstop, focus, lerp(r0, r1, u)


_p = pan_pos(-1, TILT_CUBE)
CUBE_POS = (_p[0], _p[1], _p[2] + 0.022 + CUBE / 2)       # cube resting on its pan
SHOTS = _shots()
SHAKES = [(0.0, 1.0), (T_COLLAPSE + 0.25, 1.0), (T_PULSAR, 0.6)]
