"""Shared geometry (1 unit = 1 ft): the cockpit nose on the test rig, its windshield, the impact point, the gun.

The nose points along -Y (towards the gun); s = distance back from the tip, phi = angle around the axis from the top
(+X side positive... the captain's pane is on the -X side, phi < 0).
"""
import math

import numpy as np

NOSE_R = 6.5            # fuselage radius (an A320 is ~13 ft wide)
NOSE_LN = 9.0           # length of the rounded nose
NOSE_L = 24.0           # length of the test section
NOSE_ZC = 11.0          # centre line height on the stand
NOSE_DROOP = 1.6        # the tip sits lower than the centre line


def r_of(s):
    s = np.asarray(s, float)
    u = np.clip(s / NOSE_LN, 0.0, 1.0)
    return NOSE_R * np.sqrt(np.clip(1.0 - (1.0 - u) ** 2, 0.0, 1.0)) ** 0.85


def zc_of(s):
    s = np.asarray(s, float)
    u = np.clip(s / NOSE_LN, 0.0, 1.0)
    return NOSE_ZC - NOSE_DROOP * (1.0 - u) ** 2


def surf(s, phi):
    """Point on the nose surface (lab coordinates, nose tip at y = 0)."""
    s, phi = np.broadcast_arrays(np.asarray(s, float), np.asarray(phi, float))
    r = r_of(s)
    return np.stack([r * np.sin(phi), s, zc_of(s) + r * np.cos(phi)], -1)


def normal(s, phi, h=1e-3):
    a = surf(s + h, phi) - surf(s - h, phi)
    b = surf(s, phi + h) - surf(s, phi - h)
    n = np.cross(a, b)
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    # outward: away from the axis / forward
    c = surf(s, phi) - np.stack([np.zeros_like(np.asarray(s, float)), np.asarray(s, float) + 50.0,
                                 zc_of(s)], -1)
    return np.where((np.sum(n * c, -1) < 0)[..., None], -n, n)


# windshield panes (s range, phi range) -- the captain's pane is hit
PANE_S = (4.3, 6.9)
PANE_L = (math.radians(-44), math.radians(-6))
PANE_R = (math.radians(6), math.radians(44))
SIDE_S = (6.4, 8.7)
SIDE_L = (math.radians(-80), math.radians(-52))
SIDE_R = (math.radians(52), math.radians(80))

S_I, PHI_I = 5.6, math.radians(-25)
P_I = surf(S_I, PHI_I)                       # impact point
N_I = normal(S_I, PHI_I)                     # outward normal there

# the gun fires along +Y straight at the impact point (60 ft barrel, muzzle 45 ft in front of the pane)
GUN_DIR = np.array([0.0, 1.0, 0.0])
MUZZLE = P_I - GUN_DIR * 45.0
BREECH = MUZZLE - GUN_DIR * 60.0
BORE_R = 0.62

# other props in the lab (far enough apart that each shot sees only its own)
OLD_O = np.array([90.0, 0.0, 0.0])          # the old flat windshield on its stand
SCALE_O = np.array([-90.0, -60.0, 0.0])     # bench scale
FROZ_O = np.array([-90.0, 60.0, 0.0])       # table with the frozen chicken
SKY_O = np.array([0.0, 0.0, 20000.0])       # the airliner in the sky (separate set)
