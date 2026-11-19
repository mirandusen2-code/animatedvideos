"""Narration: 'This Fluffy Cloud Weighs Over a Million Pounds'.
(key, spoken text, on-screen caption, pause after). Captions: CAPS / digits = highlighted keywords.
Every number is checked in RESEARCH.md. Works in a flat, neutral voice (no irony, no colons).
The last line flows back into the first (loop).
"""

LINES = [
    ("hook",     "This fluffy cloud weighs over a million pounds.",
                 "This fluffy cloud weighs over 1 MILLION POUNDS.", 0.35),
    ("elephants", "That's as heavy as nearly a hundred elephants.",
                 "That's as heavy as nearly 100 ELEPHANTS.", 0.45),
    ("why",      "So why doesn't it fall?", "So why doesn't it FALL?", 0.45),
    ("droplets", "Its water is split into trillions of tiny droplets.",
                 "Its water is split into TRILLIONS of tiny droplets.", 0.3),
    ("light",    "Each one is so light that rising warm air holds it up.",
                 "Each one is so LIGHT that rising warm air holds it up.", 0.45),
    ("crazy",    "But here's the crazy part.", "But here's the CRAZY part.", 0.45),
    ("air",      "The air in the same space weighs over a thousand times more.",
                 "The AIR in the same space weighs over 1,000× MORE.", 0.4),
    ("feather",  "So next time a cloud looks as light as a feather...",
                 "So next time a cloud looks as light as a feather...", 0.0),
]
