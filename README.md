# TUI Video Downloader

A small, personal terminal UI for downloading videos using [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [Textual](https://github.com/Textualize/textual).

> ⚠️ This tool is for my personal use. It comes with no support, no warranty, and no guarantees.  
> ⚠️ Make sure you follow the terms of service of any site you download from.

## Features

- Text-based UI with a live table of downloads
- Per-download progress, speed, ETA, and final file size
- Choose video + audio, audio only or video only; container (mp4, mkv, webm, mov, avi, flv) or audio format (original, mp3, m4a, opus, ogg, flac, wav, alac); video resolution and audio bitrate. Defaults to the best video quality, and your last choices are remembered
- Runs multiple downloads at once
- Press Enter on a download to see its full error and yt-dlp output; everything is also written to a log file
- Uses yt-dlp under the hood for actual downloads and format selection

## Binaries

Prebuilt builds for **Windows** (`.zip`) and **Linux** (`.AppImage` and `.tar.gz`) are on the GitHub **Releases** page. They bundle ffmpeg, ffprobe and deno, so nothing else needs installing. Unzip/extract once and run `ytdl-tui` from the folder; the AppImage runs directly.

## Running from source

You need Python 3.14+ and `uv`. Install `ffmpeg` (for best quality) and `deno` (for YouTube) on your PATH.

```bash
cd yt-dlp-tui
uv sync
uv run main.py
```

I use uv as it is faster and gives me more utilities than pip but if you want to use pip then just download the below two libs and you should be good to go.

```bash
cd yt-dlp-tui
python -m venv .venv
source .venv/bin/activate (this command is for linux (i am using debian), use the command and script for your OS)
pip install textual "yt-dlp[default]"
python main.py
```
You can skip the second and third command if you don't want a virtual env for this script to run.

By default downloads go to `~/Downloads`. You can override the path in the UI. `main.py --check` reports whether ffmpeg, ffprobe and deno are usable.

## More

- [wiki.md](wiki.md): full documentation (usage, logs, bundled tools, building, CI, bumping pinned versions)
- [ytdlp_tui/README.md](ytdlp_tui/README.md): the Python package and its modules

## License

This project is for personal use and experimentation. See `LICENCE` for details.
