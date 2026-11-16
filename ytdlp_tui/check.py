import subprocess
import sys
from pathlib import Path

import yt_dlp
from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor

from . import tools


def _deno_version(path: str) -> str | None:
    try:
        out = subprocess.run(
            [path, "eval", "console.log(Deno.version.deno)"], capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _ui_starts() -> bool:
    from .app import DownloaderApp

    async def pilot(p):
        await p.pause()
        p.app.exit()

    try:
        DownloaderApp().run(headless=True, auto_pilot=pilot)
    except Exception as e:
        print(f"UI failed to start: {type(e).__name__}: {e}")
        return False
    return True


def run_check(log_path: Path | None) -> int:
    ok = True
    print(f"yt-dlp:   {yt_dlp.version.__version__}")
    print(f"bundle:   {tools.bundled_bin_dir() or 'none (using PATH)'}")
    print(f"log file: {log_path or 'disabled'}")

    with yt_dlp.YoutubeDL({"quiet": True, **tools.ytdlp_tool_opts()}) as ydl:
        versions = FFmpegPostProcessor.get_versions(ydl)
    for prog in ("ffmpeg", "ffprobe"):
        version = versions.get(prog)
        print(f"{prog + ':':<9} {version or 'NOT FOUND'}")
        ok &= bool(version)

    deno = tools.deno_path()
    version = _deno_version(deno) if deno else None
    print(f"deno:     {f'{version} ({deno})' if version else 'NOT FOUND'}")
    ok &= bool(version)

    if getattr(sys, "frozen", False):
        bundle = tools.bundled_bin_dir()
        missing = [n for n in ("ffmpeg", "ffprobe", "deno") if not bundle or not (bundle / f"{n}{tools.EXE}").is_file()]
        if missing:
            print(f"bundled:  MISSING {', '.join(missing)}")
            ok = False

    ui = _ui_starts()
    print(f"ui:       {'ok' if ui else 'FAILED'}")
    ok &= ui

    print("result:   " + ("ok" if ok else "problems found"))
    return 0 if ok else 1
