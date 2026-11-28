"""Shared geometry for "Mentos + Diet Coke" (1 unit = 1 inch).

Sets (each far from the others; only the active set renders):
  yard   a sunny backyard lawn: a 2-liter bottle, the geyser, a basketball hoop (rim at 10 ft)
  lab    a teal studio: a see-through bottle with the dissolved gas, ghost bottles, a Mentos, Mentos sinking
  micro  the candy surface magnified in the soda: craters that spit out bubbles
"""
import math

import numpy as np

YARD_O = np.array([0.0, 0.0, 0.0])
LAB_O = np.array([1000.0, 0.0, 0.0])
MICRO_O = np.array([2000.0, 0.0, 0.0])

# ---------------------------------------------------------------- the 2-liter bottle (profile r(z), open, no cap)
BOT_PROFILE = [(0.0, 0.0), (1.55, 0.0), (1.95, 0.25), (2.08, 0.7), (2.1, 1.4), (2.1, 7.6), (2.02, 8.4),
               (1.72, 9.4), (1.25, 10.3), (0.82, 11.0), (0.6, 11.55), (0.56, 11.9), (0.68, 11.95), (0.68, 12.05),
               (0.56, 12.1), (0.56, 12.6)]
BOT_TOP = 12.6
NECK_R = 0.5                     # inner radius of the neck
FILL_Z = 9.6                     # soda level of a full bottle (just above the shoulder start)
LABEL_Z = (3.6, 6.6)


def bottle_r(z):
    p = np.array(BOT_PROFILE)
    return np.interp(z, p[:, 1], p[:, 0])


# ---------------------------------------------------------------- Mentos
MENTOS_R, MENTOS_H = 0.4, 0.3    # a 0.8 in candy, 0.3 in thick (rounded)
N_MENTOS = 6

# ---------------------------------------------------------------- the yard
HOOP_X, HOOP_Y = 34.0, 46.0      # pole base; the rim hangs toward -y
RIM_Z = 120.0                    # 10 ft
RIM_R = 9.0
G_IN = 386.0                     # gravity, in/s^2
GEYSER_H = 156.0                 # the hero geyser peaks at 13 ft
V_JET = math.sqrt(2 * G_IN * (GEYSER_H - BOT_TOP))

DIET_X = (-10.0, 10.0)           # the regular (left) and diet (right) bottles in the comparison shot
REG_H = 72.0                     # the regular soda's geyser: 6 ft
