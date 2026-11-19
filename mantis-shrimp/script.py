"""Narration: 'This Shrimp Punches at 50 MPH'  (~20 s, seamless loop).
(key, spoken text, on-screen caption, pause after). In captions: CAPS / digits = highlighted keywords,
'|' = caption chunk break (chunks written by meaning). Facts in RESEARCH.md.
Loop: "...So every punch hits twice, all because" -> "this shrimp punches at fifty miles per hour..."
"""

LINES = [
    ("hook",     "This shrimp punches at fifty miles per hour,",
                 "This shrimp PUNCHES | at 50 MILES | per hour,", 0.1),
    ("glass",    "hard enough to break glass.", "hard enough | to break GLASS.", 0.3),
    ("crazy",    "But here's the crazy part.", "But here's | the CRAZY part.", 0.25),
    ("bubbles",  "Its club is so fast, the water rips apart into tiny bubbles.",
                 "Its club is so fast, | the water RIPS apart | into tiny BUBBLES.", 0.15),
    ("collapse", "When they pop, they hit the prey a second time,",
                 "When they POP, | they hit the prey | a SECOND time,", 0.05),
    ("heat",     "with a flash of heat over seven thousand degrees Fahrenheit.",
                 "with a FLASH of heat | over 7,000 DEGREES | Fahrenheit.", 0.3),
    ("loop",     "So every punch hits twice, all because",
                 "So every punch | hits TWICE, | all because", 0.0),
]
