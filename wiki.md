# ytdl-tui wiki

## Using the app

Fill in the URL (required), an optional filename (without extension) and an optional save folder (default `~/Downloads`), pick the download options in the second row, then press Enter or the Download button. Each download runs in its own background thread, and several can run at once.

### Download options

The second row has four dropdowns. They apply to the next download you start; running downloads keep the options they started with. Your choices are remembered between launches (see [Settings file](#settings-file)). The default is Video + audio · mp4 · Best · Best.

| Dropdown | Choices | Notes |
|---|---|---|
| Mode | Video + audio, Audio only, Video only | Video only removes the audio track |
| Format (video modes) | mp4, mkv, webm, mov, avi, flv | Container of the final file |
| Format (Audio only) | Original, mp3, m4a, opus, ogg (vorbis), flac, wav, alac | Original keeps the site's audio as is (no re-encode) |
| Video | Best, 2160p, 1440p, 1080p, 720p, 480p, 360p | Disabled in Audio only |
| Audio | Best, 320k, 256k, 192k, 128k, 96k | Disabled in Video only, and for Original/flac/wav/alac |

**Video quality** picks the highest resolution at or below the choice. If the site has nothing that low, it takes the smallest resolution above it.

**Audio quality** in Video + audio mode picks the best audio stream at or below that bitrate (no re-encode, just a smaller stream). In Audio only mode with mp3/m4a/opus/ogg it's the bitrate to convert to. If the source already has the target codec (e.g. opus → opus, aac → m4a), the audio is copied without re-encoding, and the bitrate choice only steers which source stream is picked. "Best" for opus conversions means 160k.

**Containers.** Nothing is ever re-encoded to fit a container; streams are only repackaged ("remuxed"):

| Container | Streams preferred | If the streams don't fit |
|---|---|---|
| mp4 | Highest resolution, preferring mp4 video (H.264/AV1) + m4a (AAC) | Remuxed; mp4 takes almost anything except VP8 |
| webm | Highest resolution, preferring webm (VP9/AV1 + Opus) | e.g. H.264-only sites: kept as .mp4/.mkv with a warning |
| mkv | Highest resolution and best codecs | Always fits |
| mov | H.264/HEVC + AAC/MP3 first, even at a lower resolution; then anything | VP9/AV1/Opus: kept as .mkv/.webm with a warning |
| avi, flv | H.264 + AAC/MP3 first, even at a lower resolution; then anything | Kept in the original container with a warning |

Warnings show as `⚠ N warning(s)` in the status bar and under "Warnings" in the details popup (Enter).

**Without ffmpeg** (source runs only), nothing can be merged, converted or remuxed. The app picks the closest single-file stream to your choices, keeps its container, and logs a warning on the row.

### Table columns

| Column | Meaning |
|---|---|
| ID | Download number for this session |
| Title | Filename you gave, then `your name \| site title` once the info is fetched |
| Format | The options this download started with, e.g. `mp4 1080p`, `mkv best`, `mp4 720p mute` (video only), `mp3 320k`, `audio orig` |
| Status | See below |
| Size | `downloaded / total` while downloading; final file size when done |
| Progress | `percent @ speed`; for failed downloads, the start of the error |
| ETA | Time left for the current stream |
| Started | When it was queued |

### Status values

| Status | Meaning |
|---|---|
| ⏳ Queued | Thread starting |
| 🔎 Fetching info | yt-dlp is extracting info (this is when deno solves YouTube's JS challenges) |
| ⬇ Downloading / ⬇ Video 1/2 / ⬇ Audio 2/2 | Downloading; with separate video and audio streams it shows which one |
| 🔀 Merging… | ffmpeg is merging video and audio |
| 🎵 Converting… | Audio only: extracting/converting the audio |
| ⚙ Finishing… | Other post-processing (remuxing into the chosen container, removing audio, fixups, moving the file into place) |
| ✅ Done | Finished; Size shows the final file size. The status bar adds `⚠ N warning(s)` if, for example, the container had to be kept |
| ❌ Failed | See the status bar or press Enter for the full error. Known errors (currently HTTP 403) also get a hint with the likely fix |
| ⏹ Cancelled | Stopped because the app was quit |

### Keys

| Key | Action |
|---|---|
| Enter (in an input) | Start the download |
| ↑ / ↓ in the table | Highlight a download; the status bar describes the highlighted one |
| Enter (in the table) | Open details: URL, status, file path, full error and yt-dlp output (selectable for copying) |
| Esc | Close details |
| Ctrl+Q | Quit |

### Quitting during downloads

Quitting cancels every active download and waits up to 2 s for them to stop cleanly. A download that is still fetching info or merging can't stop that quickly; it is ended when the app exits. Partial `.part` files stay on disk, and yt-dlp resumes them when the same URL is downloaded again into the same folder.

## Log file

Every download's yt-dlp output (info, warnings, errors) is appended to a rotating log (1 MB, 3 backups):

| OS | Location |
|---|---|
| Linux | `$XDG_STATE_HOME/ytdl-tui/ytdl-tui.log` (default `~/.local/state/ytdl-tui/ytdl-tui.log`) |
| Windows | `%LOCALAPPDATA%\ytdl-tui\logs\ytdl-tui.log` |
| macOS | `~/Library/Logs/ytdl-tui/ytdl-tui.log` |

Lines are prefixed with the download number (`#3 ...`). The details popup shows the path.

## Settings file

The download options are saved whenever you change a dropdown:

| OS | Location |
|---|---|
| Linux | `$XDG_CONFIG_HOME/ytdl-tui/settings.json` (default `~/.config/ytdl-tui/settings.json`) |
| Windows | `%APPDATA%\ytdl-tui\settings.json` |
| macOS | `~/Library/Application Support/ytdl-tui/settings.json` |

Format: `{"download": {"mode": "av", "video_format": "mp4", "audio_format": "original", "video_quality": 0, "audio_quality": 0}}` (0 = Best). Unknown or invalid values fall back to the default for that field; a broken file is ignored. The video and audio formats are remembered separately, so switching modes restores the last format used in each.

## ffmpeg and deno

- **ffmpeg / ffprobe** merge the separate best video and best audio streams, convert audio, and remux into the chosen container. Without ffmpeg the app warns once at startup and falls back as described in [Download options](#download-options); single files are often lower quality (e.g. capped at 720p on YouTube).
- **deno** is the JavaScript runtime yt-dlp uses to solve YouTube's challenges. Without it, YouTube may offer fewer formats or fail.
- Packaged builds use the copies in `<bundle>/tools/bin`, falling back to PATH; source runs use PATH.
- `ytdl-tui --check` (or `uv run main.py --check`) prints what is found, as yt-dlp sees it, then starts the UI headless. It exits non-zero on any problem; for a packaged build that includes a tool missing from the bundle.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `HTTP Error 403: Forbidden` on YouTube, in every format | yt-dlp is too old for YouTube's current changes (seen 2026-11-17: 2026.07.04 failed, 2026.10.26 worked, with or without deno). The app shows a hint next to the error with the right fix for how you run it | Source: `uv lock --upgrade-package yt-dlp && uv sync`. Release build: use a newer release. The minimum yt-dlp in `pyproject.toml` is raised whenever an old version is confirmed broken. |
| Log says `No supported JavaScript runtime could be found` | Running from source without deno on PATH | Install deno, or use the release build (bundles deno). Some YouTube formats may be missing without it. |
| `This video is not available` | The video is private, removed, or region/age-restricted | Nothing to fix in the app. |

Check the details popup (Enter) or the log file for the full yt-dlp output.

## Release bundles

| Asset | Contents |
|---|---|
| `ytdl-tui-windows-x86_64.zip` | `ytdl-tui/ytdl-tui.exe`, `_internal/` (Python), `tools/bin/` (ffmpeg.exe, ffprobe.exe, their DLLs, deno.exe), `tools/licenses/` |
| `ytdl-tui-linux-x86_64.tar.gz` | Same layout for Linux; ffmpeg's shared libraries live in `tools/lib/` |
| `ytdl-tui-linux-x86_64.AppImage` | The Linux folder packed as an AppImage (mounted, not unpacked, so it starts fast) |

Size: about 340 MB unpacked (tools ~285 MB, Python ~45 MB); downloads are about 145–155 MB. The Linux build needs glibc 2.35+ (Debian 12, Ubuntu 22.04 or newer).

Bundled versions (pinned in `scripts/build.py`):

| Tool | Version | Source |
|---|---|---|
| ffmpeg + ffprobe | n9.0.2-39-g7adfbe40dc, GPL shared build | BtbN/FFmpeg-Builds `autobuild-2026-10-31-12-59` |
| deno | 2.9.8 | denoland/deno |
| appimagetool | continuous (SHA-256 pinned) | AppImage/appimagetool |
| AppImage runtime | 20251108 | AppImage/type2-runtime |

ffmpeg is GPL-licensed; its licence ships in `tools/licenses/`. This project is GPL-3.0 too.

## Development

```bash
uv sync                      # app + dev tools (pytest, ruff)
uv run pytest                # tests: real yt-dlp against a local HTTP server, no internet needed
uv run python scripts/build.py --tools-only build/test-tools   # optional: pinned ffmpeg/deno for tests
PATH="$PWD/build/test-tools/tools/bin:$PATH" uv run pytest
uv run ruff check .
uv run main.py --check
```

Tests cover: final size and path, custom filename, single extraction, the ffmpeg fallback, full error text, cancellation, markup-safe rendering, status bar follow, the details popup, quitting mid-download, stream selection for every option (against a synthetic YouTube-like format list), settings persistence, the options dropdowns, and real-ffmpeg end-to-end conversions (remux, kept containers, audio removal, mp3/m4a/flac extraction). The end-to-end tests are skipped when ffmpeg/ffprobe aren't on PATH; CI runs them with the pinned build.

## Building locally

```bash
uv sync --group build
uv run python scripts/build.py                    # current OS; Linux also builds the AppImage
uv run python scripts/build.py --no-appimage      # Linux, skip AppImage
dist/ytdl-tui/ytdl-tui --check
```

Downloads are cached in `build/downloads/` and verified against their SHA-256 on every build. Outputs land in `dist/`. Windows builds must run on Windows (PyInstaller doesn't cross-compile).

## CI (`.github/workflows/package.yaml`)

| Trigger | What runs |
|---|---|
| Pull request, push to `main`, manual run | Lint & test (with the pinned ffmpeg/deno on PATH) → build both platforms → smoke test → upload artifacts |
| Push of a `v*` tag | Same, then a GitHub Release with git-cliff changelog and the three assets (tags with `-`, e.g. `v1.0-rc1`, become prereleases) |

Pinned: every action by commit SHA (with its version in a comment), uv version, runner images (`ubuntu-22.04`, `windows-2025`), Python deps via `uv.lock` (including PyInstaller in the `build` group), and the tools above via `scripts/build.py`.

Pinned tool downloads are cached (`build/downloads`, keyed on `scripts/build.py`), so they're only fetched again when a pin changes.

Dependabot (`.github/dependabot.yml`) opens a grouped PR monthly for actions and weekly for Python deps.

## Bumping pinned tools

Dependabot doesn't see `scripts/build.py`, so bump these by hand:

1. Pick the new release (ffmpeg: a month-end `autobuild-YYYY-MM-31-…` tag from BtbN/FFmpeg-Builds, since daily builds are deleted after ~2 weeks).
2. Copy the asset's SHA-256 from the GitHub release page (each asset shows a `sha256:` digest), or download it and run `sha256sum`.
3. Update the URL and hash in `scripts/build.py`, build locally, run `--check`.
4. Update the table in this wiki.

appimagetool only publishes a `continuous` build. When upstream rebuilds it, CI fails with `checksum mismatch for appimagetool-x86_64.AppImage`; update its hash the same way.

To bump uv, change `UV_VERSION` in the workflow.
