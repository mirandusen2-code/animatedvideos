"""Narration: 'Never Eat This Beetle'  (~18 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...So whatever you do," -> "never eat this beetle."
"""

LINES = [
    ("hook",    "Never eat this beetle.", "NEVER eat | this BEETLE.", 0.2),
    ("spray",   "It shoots boiling hot spray out of its butt.",
                "It shoots | BOILING hot spray | out of its BUTT.", 0.25),
    ("temp",    "Two chemicals mix inside it and explode, at two hundred twelve degrees Fahrenheit.",
                "Two CHEMICALS | mix inside it | and EXPLODE, | at 212 DEGREES | Fahrenheit.", 0.3),
    ("twist",   "Even if a toad swallows it, it keeps firing inside its stomach,",
                "Even if a TOAD | SWALLOWS it, | it keeps FIRING | inside its STOMACH,", 0.05),
    ("vomit",   "until the toad throws it back up, alive.",
                "until the toad | throws it BACK UP, | ALIVE.", 0.25),
    ("loop",    "So whatever you do,", "So WHATEVER | you do,", 0.0),
]
