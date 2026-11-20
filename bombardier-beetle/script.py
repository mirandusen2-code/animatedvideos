"""Narration: 'This Beetle Shoots Boiling Spray Out of Its Butt'  (~20 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...And it walks away, because" -> "this beetle shoots boiling hot spray out of its butt..."
"""

LINES = [
    ("hook",    "This beetle shoots boiling hot spray out of its butt.",
                "This beetle shoots | BOILING hot spray | out of its BUTT.", 0.25),
    ("temp",    "Two chemicals mix inside it and explode, at two hundred twelve degrees Fahrenheit.",
                "Two CHEMICALS | mix inside it | and EXPLODE, | at 212 DEGREES | Fahrenheit.", 0.3),
    ("crazy",   "But here's the crazy part.", "But here's | the CRAZY part.", 0.25),
    ("swallow", "When a toad swallows it, it keeps firing inside its stomach,",
                "When a toad | SWALLOWS it, | it keeps FIRING | inside its STOMACH,", 0.1),
    ("vomit",   "until the toad throws it back up, alive.",
                "until the toad | throws it BACK UP, | ALIVE.", 0.35),
    ("loop",    "And it walks away, because", "And it walks away, | because", 0.0),
]
