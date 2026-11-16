import re
import sys


def _update_instructions() -> str:
    if getattr(sys, "frozen", False):
        return "download the newest ytdl-tui release"
    return "run `uv lock --upgrade-package yt-dlp && uv sync`"


HINTS = [
    (
        re.compile(r"HTTP Error 403"),
        lambda: f"yt-dlp may be outdated (sites change often); to update, {_update_instructions()}",
    ),
]


def hint_for(error: str) -> str:
    for pattern, make in HINTS:
        if pattern.search(error):
            return make()
    return ""
