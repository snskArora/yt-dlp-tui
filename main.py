# main.py
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Button, DataTable, Static
from textual.containers import Vertical, Horizontal
from textual.widgets._data_table import CellDoesNotExist
from textual import work, events

import yt_dlp
import os
from datetime import datetime


# ── Fixed column definitions (label, width) ───────────────────────────────────
LEFT_COLS = [("ID", 4)]
RIGHT_COLS = [
    ("Status",     16),
    ("Size",       23),   # "142.3 MB / 980.0 MB"
    ("Progress",   22),   # "100.0% @ 10.00 MiB/s"
    ("ETA",         8),
    ("Started At", 10),
]

FIXED_WIDTH = sum(w for _, w in LEFT_COLS + RIGHT_COLS)
N_COLS      = len(LEFT_COLS) + 1 + len(RIGHT_COLS)   # +1 for Title
SEPARATORS  = N_COLS - 1


def fmt_size(b) -> str:
    if b is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


class DownloaderApp(App):
    CSS = """
    Screen { background: $surface; }


    #top-bar {
        height: auto;
        padding: 0 2;
        background: $panel;
        border-bottom: solid $primary;
    }
    #input-row { height: auto; align: left middle; }

    #url-input  { width: 3fr; }
    #path-input { width: 2fr; }
    #btn-download { width: auto; margin-left: 1; min-width: 14; }

    #download-table { height: 1fr; border: none; background: $surface; }

    #status-bar {
        height: 1;
        padding: 0 2;
        background: $panel;
        border-top: solid $primary;
        content-align: left middle;
        color: $text-muted;
    }
    """


    def __init__(self):
        super().__init__()
        self.download_counter  = 0
        self.downloads: dict[int, dict] = {}
        self._col_keys: dict[str, object] = {}
        self._title_col_width: int = 40   # updated on every resize

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="top-bar"):
            with Horizontal(id="input-row"):
                yield Input(placeholder="Video URL…", id="url-input")
                yield Input(placeholder="Save path (~/Downloads)", id="path-input")
                yield Button("⬇ Download", variant="primary", id="btn-download")
        yield DataTable(id="download-table", show_cursor=True, zebra_stripes=True)
        yield Static("Ready.", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.cursor_type = "row"

        keys: list[tuple[str, object]] = []
        for label, width in LEFT_COLS:
            keys.append((label, table.add_column(label, width=width)))

        # Title placeholder — width corrected once layout is known
        keys.append(("Title", table.add_column("Title", width=self._title_col_width)))

        for label, width in RIGHT_COLS:
            keys.append((label, table.add_column(label, width=width)))

        self._col_keys = {label: key for label, key in keys}
        self.call_after_refresh(self._resize_title_col)

    def on_resize(self, event: events.Resize) -> None:
        self._resize_title_col()

    def _calc_title_width(self) -> int:
        return max(12, self.size.width - FIXED_WIDTH - SEPARATORS - 2)

    def _resize_title_col(self) -> None:
        """Update the Title column width to fill remaining terminal space."""
        if "Title" not in self._col_keys:
            return

        title_w = self._calc_title_width()
        self._title_col_width = title_w


        table   = self.query_one(DataTable)
        col_key = self._col_keys["Title"]


        # ── Try to resize the column itself (internal API, version-dependent) ──
        # Textual stores columns in _columns (older) or columns (newer).

        # We try both; if neither works we fall through to text truncation.

        _resized = False
        for attr in ("_columns", "columns"):
            col_store = getattr(table, attr, None)
            if not isinstance(col_store, dict):
                continue
            col_obj = col_store.get(col_key)
            if col_obj is not None and hasattr(col_obj, "width"):
                try:
                    col_obj.width = title_w
                    _resized = True
                    break
                except Exception:

                    pass

        if _resized:
            # Flush layout caches if available
            for method in ("_clear_caches", "clear_caches", "_invalidate"):
                if hasattr(table, method):
                    try:
                        getattr(table, method)()

                    except Exception:
                        pass

        table.refresh()

        # ── Always truncate text in Title cells to the new width ──────────────
        # This acts as the primary approach when column resize isn't possible,
        # and as a visual cleanup pass when it is possible.
        for dl_id, info in self.downloads.items():
            full_title = info.get("full_title") or info.get("url", "")
            truncated  = full_title[:title_w]
            row_key    = info["row_key"]
            try:
                table.update_cell(row_key, col_key, truncated)
            except CellDoesNotExist:
                pass


    # ── Input events ──────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-download":
            self.start_download()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("url-input", "path-input"):
            self.start_download()

    # ── Queueing ──────────────────────────────────────────────────────────────

    def start_download(self) -> None:
        url_input  = self.query_one("#url-input",  Input)
        path_input = self.query_one("#path-input", Input)


        url       = url_input.value.strip()
        save_path = path_input.value.strip() or os.path.expanduser("~/Downloads")

        if not url:
            self.query_one("#status-bar", Static).update("⚠  Please enter a URL.")
            return

        self.download_counter += 1
        dl_id      = self.download_counter
        started_at = datetime.now().strftime("%H:%M:%S")
        title_w    = self._title_col_width

        table   = self.query_one(DataTable)
        row_key = table.add_row(
            str(dl_id),
            url[:title_w],          # initial display: URL truncated to col width
            "⏳ Queued", "—", "—", "—", started_at,
            key=f"dl_{dl_id}",
        )


        self.downloads[dl_id] = {
            "url":        url,
            "full_title": url,      # overwritten once yt-dlp fetches the real title
            "row_key":    row_key,
        }
        url_input.clear()
        self.query_one("#status-bar", Static).update(
            f"🚀  Download #{dl_id} queued — {url[:60]}"
        )
        self.run_download(dl_id, url, save_path)

    # ── Worker ────────────────────────────────────────────────────────────────

    @work(exclusive=False, thread=True)
    def run_download(self, dl_id: int, url: str, save_path: str) -> None:
        row_key = self.downloads[dl_id]["row_key"]


        def update(status: str, size: str = "—", progress: str = "—", eta: str = "—"):
            def _update():
                try:
                    table = self.query_one(DataTable)
                    table.update_cell(row_key, self._col_keys["Status"],   status)
                    table.update_cell(row_key, self._col_keys["Size"],     size)
                    table.update_cell(row_key, self._col_keys["Progress"], progress)
                    table.update_cell(row_key, self._col_keys["ETA"],      eta)
                    self.query_one("#status-bar", Static).update(
                        f"#{dl_id}: {status}  {size}  {progress}  ETA {eta}"
                    )
                except CellDoesNotExist:
                    pass
            self.call_from_thread(_update)

        def set_title(title: str):
            # Persist the full title so _resize_title_col can re-truncate on resize
            self.downloads[dl_id]["full_title"] = title

            def _set():

                try:

                    truncated = title[:self._title_col_width]
                    self.query_one(DataTable).update_cell(

                        row_key, self._col_keys["Title"], truncated
                    )
                except CellDoesNotExist:
                    pass

            self.call_from_thread(_set)

        def progress_hook(d: dict):
            if d["status"] == "downloading":
                percent  = d.get("_percent_str", "?").strip()
                speed    = d.get("_speed_str",   "?").strip()
                eta      = d.get("_eta_str",     "?").strip()
                dl_bytes = d.get("downloaded_bytes")
                tot      = d.get("total_bytes") or d.get("total_bytes_estimate")
                update("⬇  Downloading",
                       f"{fmt_size(dl_bytes)} / {fmt_size(tot)}",
                       f"{percent} @ {speed}", eta)
            elif d["status"] == "finished":
                update("🔀 Merging…", progress="100%")

        def postprocessor_hook(d: dict):
            if d["status"] == "finished":
                filename = os.path.basename(d.get("filename", ""))

                filepath = d.get("filepath")
                fsize    = os.path.getsize(filepath) if filepath and os.path.exists(filepath) else None
                set_title(filename)
                update("✅ Done", fmt_size(fsize), "100%", "—")

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",

            "merge_output_format": "mp4",
            "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),

            "progress_hooks": [progress_hook],
            "postprocessor_hooks": [postprocessor_hook],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            update("⏳ Fetching info…")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                set_title(info.get("title", url))
                update("⬇  Starting…")
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            update("❌ Failed", progress=str(e)[:40])
        except Exception as e:
            update("❌ Error",  progress=str(e)[:40])


if __name__ == "__main__":
    DownloaderApp().run()
