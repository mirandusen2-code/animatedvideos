"""Shared timeline for 'What if you jumped through the Earth?' (used by Blender + post)."""
import math

FPS = 30
DUR = 35.0
NFRAMES = int(DUR * FPS)

R = 1.0             # Earth radius (scene units)
H = 0.07            # person height
X0 = 0.06           # distance from the hole where the person stands
OFF = 0.03          # person sits in front of the tunnel corner during the fall
T_JUMP, T_IN, T_ARRIVE, T_BACK = 1.6, 2.4, 28.0, 29.6
A = R + H / 4       # z_center = A*cos(phase) + B
B = H / 4
REAL_MINUTES = 38.0  # Klotz (2015), realistic density model


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def lerp(a, b, x):
    return a + (b - a) * x


def lerpv(a, b, x):
    return tuple(lerp(p, q, x) for p, q in zip(a, b))


def phase(t):
    """0 at the north pole, pi at the south pole, 2*pi back north."""
    if t < T_IN:
        return 0.0
    if t < T_ARRIVE:
        return math.pi * (t - T_IN) / (T_ARRIVE - T_IN)
    if t < T_BACK:
        return math.pi
    return math.pi + math.pi * (t - T_BACK) / (T_ARRIVE - T_IN)


def person(t):
    """(x, y, z) centre, rot_x, rot_z"""
    sx, sy = -X0 * 0.7, X0 * 0.7
    zs = math.sqrt(R * R - X0 * X0) + H / 2
    if t < T_JUMP:
        return (sx, sy, zs + 0.004 * math.sin(t * 6)), 0.0, 0.0
    if t < T_IN:
        u = (t - T_JUMP) / (T_IN - T_JUMP)
        x = lerp(sx, OFF, ease(u))
        y = lerp(sy, OFF, ease(u))
        z = lerp(zs, A + B, u) + 0.07 * math.sin(math.pi * u)
        return (x, y, z), 0.0, 0.0
    ph = phase(t)
    z = A * math.cos(ph) + B
    rx = math.pi * ease((t - 6.0) / 14.0)
    rz = 0.8 + 1.4 * (t - T_IN)
    return (OFF, OFF, z), rx, rz


def speed_frac(t):
    return abs(math.sin(phase(t)))


def minutes(t):
    """Elapsed 'real' minutes shown on the timer."""
    if t < T_IN:
        return 0.0
    return REAL_MINUTES * phase(t) / math.pi


# ---------------------------------------------------------------- camera
WIDE = ((1.05, 3.25, 1.05), (0.02, 0.0, -0.02))


def shot(name, t):
    if name == "north":
        return (0.18, 0.42, 1.12), (0.0, 0.02, 1.0)
    if name == "wide":
        return WIDE
    if name == "track":
        z = person(t)[0][2]
        return (0.30, 0.78, z + 0.13), (0.03, 0.03, z - 0.01)
    if name == "south":
        return (0.18, 0.44, -1.08), (0.02, 0.03, -1.035)


# (start_time, shot) ; transitions blend over the gap until the next start
CUTS = [
    (0.0, "north", 2.6),     # (start, shot, time when the move to the next shot starts)
    (5.2, "wide", 6.6),
    (8.6, "track", 24.4),
    (26.6, "south", 29.9),
    (32.4, "wide", 99),
]


def camera(t):
    for i, (t0, name, tmove) in enumerate(CUTS):
        nxt = CUTS[i + 1] if i + 1 < len(CUTS) else None
        if nxt is None or t < tmove:
            return shot(name, t)
        if t < nxt[0]:
            u = ease((t - tmove) / (nxt[0] - tmove))
            p1, a1 = shot(name, t)
            p2, a2 = shot(nxt[1], t)
            return lerpv(p1, p2, u), lerpv(a1, a2, u)
    return shot(CUTS[-1][1], t)


# label anchors on the cut face (x, y, z) and when they show
LABELS = [
    ("CRUST", (0.18, 0.0, 0.975), 6.8, 9.6),
    ("MANTLE", (0.22, 0.0, 0.74), 8.8, 12.2),
    ("OUTER CORE", (0.20, 0.0, 0.38), 10.6, 14.2),
    ("INNER CORE", (0.12, 0.0, 0.06), 12.6, 18.0),
]

# captions (word chunks), the voiceover script
CAPTIONS = [
    (0.0, 1.4, "If you jumped into"),
    (1.4, 2.7, "a hole through the EARTH,"),
    (2.7, 4.0, "you'd come out the other side"),
    (4.0, 5.3, "in just 38 MINUTES."),
    (5.5, 7.3, "Here's what happens on the way."),
    (7.4, 9.5, "You fall FASTER and faster..."),
    (9.6, 12.0, "past the mantle, into liquid metal..."),
    (12.1, 15.0, "to a center almost as HOT as the Sun's surface."),
    (15.1, 18.0, "By now you're going 28,000+ KM/H."),
    (18.2, 19.7, "But here's the CRAZY part:"),
    (19.8, 22.6, "at the center, gravity pulls from EVERY side..."),
    (22.7, 25.1, "so now it starts SLOWING you down."),
    (25.2, 28.0, "38 minutes later, you reach the other side..."),
    (28.1, 29.7, "STOP for a split second..."),
    (29.8, 31.4, "and fall ALL the way back."),
    (31.5, 33.0, "Forever. Because..."),
    (33.0, 35.0, "if you jumped into a hole through the Earth..."),
]
