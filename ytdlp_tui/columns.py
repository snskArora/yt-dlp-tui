# ── Fixed column definitions (label, width) ───────────────────────────────────
LEFT_COLS = [("ID", 4)]
RIGHT_COLS = [
    ("Format",     15),   # "webm 1440p mute"
    ("Status",     16),
    ("Size",       19),   # "142.3 MB / 980.0 MB"
    ("Progress",   20),   # "100.0% @ 999.9 MB/s"
    ("ETA",         8),
    ("Started",     8),
]

FIXED_WIDTH = sum(w for _, w in LEFT_COLS + RIGHT_COLS)
N_COLS      = len(LEFT_COLS) + 1 + len(RIGHT_COLS)   # +1 for Title
