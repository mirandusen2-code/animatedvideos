"""Narration script. Each line: (key, spoken text, on-screen caption, pause after in seconds).

Spoken text is written for the ear (numbers in words, '...' for pauses); captions are written for the eye.
Words in CAPS or with digits in a caption are highlighted.
"""

LINES = [
    ("hook",      "This sugar cube weighs more than every human on Earth...",
                  "This sugar cube weighs more than every HUMAN on Earth", 0.25),
    ("combined",  "combined.", "COMBINED.", 0.55),
    ("notsugar",  "Because it isn't sugar.", "Because it isn't SUGAR.", 0.25),
    ("neutron",   "It's a piece of a neutron star.", "It's a piece of a NEUTRON STAR.", 0.45),
    ("dies",      "When a giant star dies, its core collapses,",
                  "When a giant star dies, its core COLLAPSES,", 0.15),
    ("squeeze",   "squeezing more mass than our Sun into a ball just twenty kilometers, or twelve miles, wide.",
                  "squeezing more mass than our SUN into a ball just 20 KM (12 MILES) wide.", 0.3),
    ("city",      "About the size of a city.", "About the size of a CITY.", 0.5),
    ("crazy",     "But here's the crazy part.", "But here's the CRAZY part.", 0.45),
    ("spin",      "Some of them spin over seven hundred times...", "Some of them spin over 700 TIMES", 0.15),
    ("second",    "every second.", "every SECOND.", 0.55),
    ("billion",   "So one sugar cube of it, here on Earth, would weigh a billion tons.",
                  "So one sugar cube of it, here on Earth, would weigh a BILLION TONS.", 0.35),
    ("why",       "And that's why...", "And that's why...", 0.0),
]
