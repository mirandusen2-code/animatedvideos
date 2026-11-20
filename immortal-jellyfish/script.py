"""Narration: 'This Jellyfish Can Live Forever'  (~18 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...So unless something eats it," -> "this jellyfish can live forever."
"""

LINES = [
    ("hook",  "This jellyfish can live forever.", "This JELLYFISH | can live FOREVER.", 0.25),
    ("old",   "When it gets old or hurt, it doesn't die.", "When it gets OLD | or HURT, | it doesn't DIE.", 0.2),
    ("melt",  "It melts into a tiny blob, sinks to the sea floor,", "It MELTS | into a tiny BLOB, | sinks to the SEA FLOOR,", 0.05),
    ("baby",  "and turns back into a baby.", "and turns back | into a BABY.", 0.3),
    ("cells", "Its old cells become brand new ones, and it grows up all over again.",
              "Its OLD cells | become brand NEW ones, | and it GROWS UP | all over AGAIN.", 0.25),
    ("again", "Again, and again, and again.", "AGAIN, | and AGAIN, | and AGAIN.", 0.3),
    ("loop",  "So unless something eats it,", "So unless something | EATS it,", 0.0),
]
