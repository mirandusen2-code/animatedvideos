"""Narration: 'The Moon Is Running Away From Us'  (~20 s, seamless loop).
(key, spoken text, on-screen caption, pause after). CAPS / digits = highlighted keywords, '|' = caption chunk break.
Loop: "...And it's still leaving. Right now," -> "the Moon is running away from us."
"""

LINES = [
    ("hook",    "The Moon is running away from us.", "The MOON | is RUNNING AWAY | from us.", 0.3),
    ("rate",    "Every year, it drifts an inch and a half farther away.", "Every YEAR, | it drifts 1.5 INCHES | farther away.", 0.05),
    ("nails",   "That's about as fast as your fingernails grow.", "That's about as fast | as your FINGERNAILS grow.", 0.3),
    ("past",    "When it was born, it was so close it filled the sky,", "When it was BORN, | it was so CLOSE | it filled the SKY,", 0.05),
    ("day",     "and a day on Earth lasted about six hours.", "and a DAY on Earth | lasted about 6 HOURS.", 0.3),
    ("eclipse", "In six hundred million years, it'll be too far away to cover the Sun.",
                "In 600 MILLION years, | it'll be too FAR | to cover the SUN.", 0.3),
    ("loop",    "And it's still leaving. Right now,", "And it's still LEAVING. | Right NOW,", 0.0),
]
