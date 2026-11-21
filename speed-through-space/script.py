"""Narration: 'You're Moving at 500,000 MPH'  (~21 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...So even when you're sitting perfectly still," -> "you're moving at half a million miles an hour."
"""

LINES = [
    ("hook",   "You're moving at half a million miles an hour.", "You're MOVING at | 500,000 MPH.", 0.3),
    ("spin",   "Earth spins you around,", "EARTH | spins you around,", 0.05),
    ("orbit",  "it races around the Sun,", "it RACES | around the SUN,", 0.05),
    ("galaxy", "and the Sun drags all of us around the galaxy.", "and the SUN drags | all of us | around the GALAXY.", 0.3),
    ("lap",    "One trip around takes two hundred and thirty million years.", "One TRIP around | takes 230 MILLION YEARS.", 0.3),
    ("dino",   "Last time we were here, the first dinosaurs were just appearing.",
               "Last time | we were HERE, | the first DINOSAURS | were just appearing.", 0.35),
    ("loop",   "So even when you're sitting perfectly still,", "So even when you're | sitting perfectly STILL,", 0.0),
]
