import os
import shutil
import sys
from pathlib import Path

EXE = ".exe" if os.name == "nt" else ""


def bundled_bin_dir() -> Path | None:
    if not getattr(sys, "frozen", False):
        return None
    path = Path(sys.executable).resolve().parent / "tools" / "bin"
    return path if path.is_dir() else None


def find_tool(name: str) -> str | None:
    bundled = bundled_bin_dir()
    if bundled and (bundled / f"{name}{EXE}").is_file():
        return str(bundled / f"{name}{EXE}")
    return shutil.which(name)


def ffmpeg_path() -> str | None:
    return find_tool("ffmpeg")


def deno_path() -> str | None:
    return find_tool("deno")


def ytdlp_tool_opts() -> dict:
    opts: dict = {}
    if ffmpeg := ffmpeg_path():
        opts["ffmpeg_location"] = ffmpeg
    if deno := deno_path():
        opts["js_runtimes"] = {"deno": {"path": deno}}
    return opts
