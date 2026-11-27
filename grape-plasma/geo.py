"""Shared geometry for "Grapes in a microwave make plasma" (1 unit = 1 inch).

Sets (each far from the others; only the active set renders):
  mw    inside a microwave oven: glass turntable, two grapes touching, the plasma fireball (frame 0 / loop)
  lab   a dark navy studio for the explanation: waves, a water block, cut-away grapes, the hotspot, a pin
  zoom  the hotspot magnified: salt ions with electrons, ripped off into plasma
"""
import math

import numpy as np

MW_O = np.array([0.0, 0.0, 0.0])
LAB_O = np.array([1000.0, 0.0, 0.0])
ZOOM_O = np.array([2000.0, 0.0, 0.0])

# ---------------------------------------------------------------- microwave oven interior
MW_X, MW_Y, MW_Z = 7.5, 7.0, 9.0          # half width, half depth, height (door at -Y, camera side)
TT_R, TT_Z = 5.6, 0.75                    # turntable radius and top height
TT_W = 0.55                               # turntable spin (rad/s, ~5 rpm)

# ---------------------------------------------------------------- the grapes (lying on their side, long axis along Y)
GR_A = (0.40, 0.52, 0.40)                 # semi-axes x, y, z (a 0.8 x 1.04 in grape)
CONTACT_Z = TT_Z + GR_A[2]                # height of the touching point (grape centres at x = +-GR_A[0])


def grape_centres(origin, z=None):
    o = np.asarray(origin, float)
    zz = CONTACT_Z if z is None else z
    return [o + np.array([-GR_A[0], 0.0, zz]), o + np.array([GR_A[0], 0.0, zz])]


def contact(origin, z=None):
    return np.asarray(origin, float) + np.array([0.0, 0.0, CONTACT_Z if z is None else z])


# ---------------------------------------------------------------- the waves
LAM_AIR = 4.8                             # 2.45 GHz microwave in air: 12.2 cm = 4.8 in
LAM_WATER = 0.53                          # in water (refractive index ~9 at 2.45 GHz): ~1.35 cm = 0.53 in
WAVE_Z = 3.2                              # height of the demo wave above the lab floor
WATER_X0 = 3.0                            # the water block starts here (lab coords, x)

LAB_GRAPES = np.array([-0.5, 2.5, 0.0])   # where the lab grape pair sits (relative to LAB_O)
LAB_GZ = GR_A[2]                          # they rest on the lab floor


def sine_path(x0, x1, lam, amp, phase, n, z=0.0, y=0.0):
    """Points along a travelling sine wave in the x-z plane."""
    x = np.linspace(x0, x1, n)
    zz = z + amp * np.sin(2 * math.pi * (x - x0) / lam - phase)
    return np.stack([x, np.full(n, y), zz], -1)


def ellipse_bounce(a, b, n_hits, start_ang=0.35, step=2.35):
    """A ray bouncing inside an ellipse (the 'whispering gallery' star): returns the hit points (n, 2)."""
    ang = start_ang + step * np.arange(n_hits)
    return np.stack([a * np.cos(ang), b * np.sin(ang)], -1)
