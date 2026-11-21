"""Narration: 'Lightning Is 5x Hotter Than the Sun'  (~20 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...So next time you see one, remember:" -> "this is five times hotter than the Sun."
"""

LINES = [
    ("hook",    "This is five times hotter than the Sun.", "This is | 5X HOTTER | than the SUN.", 0.3),
    ("heat",    "A lightning bolt heats the air to fifty thousand degrees.", "A LIGHTNING bolt | heats the air | to 50,000 DEGREES.", 0.05),
    ("sun",     "The surface of the Sun is about ten thousand.", "The surface | of the SUN | is about 10,000.", 0.3),
    ("boom",    "The air heats up so fast, it explodes. That's thunder.", "The air heats up | so FAST, | it EXPLODES. | That's THUNDER.", 0.3),
    ("inch",    "And the bolt is only about an inch wide.", "And the bolt | is only about | an INCH wide.", 0.3),
    ("count",   "It strikes about forty-four times every second, somewhere on Earth.",
                "It strikes | about 44 TIMES | every SECOND, | somewhere on EARTH.", 0.3),
    ("loop",    "So next time you see one, remember:", "So next time | you SEE one, | remember:", 0.0),
]
