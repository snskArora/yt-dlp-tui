import argparse
import sys

from ytdlp_tui.app import DownloaderApp
from ytdlp_tui.check import run_check
from ytdlp_tui.logs import setup_logging
from ytdlp_tui.settings import Settings, default_settings_path


def main() -> int:
    parser = argparse.ArgumentParser(prog="ytdl-tui", description="Terminal UI for yt-dlp downloads.")
    parser.add_argument(
        "--check", action="store_true", help="check that ffmpeg, ffprobe, deno and the UI work, then exit"
    )
    args = parser.parse_args()
    log_path = setup_logging()
    if args.check:
        return run_check(log_path)
    DownloaderApp(log_path=log_path, settings=Settings(default_settings_path())).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
