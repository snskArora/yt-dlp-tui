# ytdlp_tui

The application package. `main.py` at the repo root is the entry point.

| Module | Role |
|---|---|
| `downloader.py` | UI-agnostic core: the `Job` model, `State` enum and `run(job, notify)`, which drives yt-dlp and reports changes through `notify`. Cancel via `job.cancel`. |
| `options.py` | UI-agnostic download options (`DownloadOptions`, `Mode`, choice lists) and their translation into yt-dlp params. |
| `container.py` | yt-dlp postprocessor that remuxes into the chosen container (or strips audio) without re-encoding, keeping the file as is when impossible. |
| `settings.py` | Remembered options (`settings.json`) location, load and save. |
| `tools.py` | Finds ffmpeg/ffprobe/deno: the bundled `tools/bin` in a packaged build, otherwise PATH. |
| `app.py` | Textual UI: inputs, options dropdowns, download table, status bar, one daemon thread per download, quit handling. |
| `details.py` | Modal with a download's full error and yt-dlp output. |
| `check.py` | `--check` self-test used by CI. |
| `logs.py` | Rotating log file setup and location. |
| `naming.py` | Output filename template and display title. |
| `columns.py`, `formatting.py` | Table column widths; size and duration formatting. |

Details live in [../wiki.md](../wiki.md).
