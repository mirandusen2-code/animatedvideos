"""Narration: 'You're Moving at 500,000 MPH'  (~21 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...And even when you're sitting perfectly still," -> "you're moving at half a million miles an hour."
"""

LINES = [
    ("hook",   "You're moving at half a million miles an hour.", "You're MOVING at | 500,000 MPH.", 0.3),
    ("spin",   "Earth spins you around at up to a thousand miles an hour,", "EARTH spins you around | at up to 1,000 MPH,", 0.05),
    ("orbit",  "while it races around the Sun at sixty-seven thousand.", "while it RACES | around the SUN | at 67,000.", 0.3),
    ("galaxy", "And the Sun drags all of us around the galaxy at five hundred thousand.",
               "And the SUN | drags all of us | around the GALAXY | at 500,000.", 0.3),
    ("lap",    "One trip around takes two hundred and thirty million years.", "One TRIP around | takes 230 MILLION YEARS.", 0.3),
    ("dino",   "Last time we were here, the first dinosaurs were just appearing.",
               "Last time | we were HERE, | the first DINOSAURS | were just appearing.", 0.35),
    ("loop",   "And even when you're sitting perfectly still,", "And even when you're | sitting perfectly STILL,", 0.0),
]
