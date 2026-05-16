# TUI Video Downloader

A small, personal terminal UI for downloading videos using [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [Textual](https://github.com/Textualize/textual).

> ⚠️ This tool is for my personal use. It comes with no support, no warranty, and no guarantees.  
> ⚠️ Make sure you follow the terms of service of any site you download from.

## Features

- Text-based UI with a live table of downloads
- Per-download progress, speed, ETA, and final file size
- Queues multiple URLs
- Uses yt-dlp under the hood for actual downloads and format selection

## Binaries

Prebuilt binaries for **Windows** and **Linux (binary + AppImage)** are available on the GitHub **Releases / Packages** page for this repository.

If you just want to use the tool, grab the appropriate binary for your platform from there.

## Running from source

You need a recent Python (3.14+ recommended) and `uv`.
```bash
cd video-downloader-tui
uv sync
uv run main.py
```

I use uv as it is faster and gives me more utilities than pip but if you want to use pip then just download the below two libs and you should be good to go.

```bash
cd video-downloader-tui
python -m venv .venv
source .venv/bin/activate (this command is for linux (i am using debian), use the command and script for your OS)
pip install textual yt-dlp
python main.py
```
You can skip the second and third commadn if you dont want a virtual env for this script to run.


By default downloads go to `~/Downloads`. You can override the path in the UI.

## License

This project is for personal use and experimentation. See `LICENCE` for details.
