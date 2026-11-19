"""Narration: 'This Tiny Animal Survived 10 Days in Open Space'.
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...still be up there." -> "This tiny animal survived ten days in open space."
"""

LINES = [
    ("hook",   "This tiny animal survived ten days in open space.",
               "This tiny animal | survived 10 DAYS | in open SPACE.", 0.25),
    ("size",   "It's a tardigrade, barely half a millimeter long.",
               "It's a TARDIGRADE, | barely half | a millimeter long.", 0.3),
    ("dries",  "To survive, it dries itself out, losing almost all its water,",
               "To survive, | it DRIES itself out, | losing almost | ALL its water,", 0.15),
    ("wakes",  "and comes back to life when it gets wet again.",
               "and comes back to LIFE | when it gets wet again.", 0.35),
    ("babies", "After the trip, some even had babies.",
               "After the trip, | some even had BABIES.", 0.35),
    ("crazy",  "But here's the crazy part.", "But here's | the CRAZY part.", 0.3),
    ("moon",   "In 2019, thousands of them crash-landed on the Moon.",
               "In 2019, | THOUSANDS of them | crash-landed on the MOON.", 0.25),
    ("still",  "And they might still be up there.", "And they might | still be up there.", 0.0),
]
