import asyncio
import logging
import os
import threading
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Select, Static
from textual.widgets._data_table import CellDoesNotExist

from . import downloader, tools
from .columns import FIXED_WIDTH, LEFT_COLS, N_COLS, RIGHT_COLS
from .details import DetailsScreen
from .downloader import ACTIVE_STATES, Job, State
from .logs import LOGGER_NAME
from .options import (
    AUDIO_FORMATS,
    AUDIO_QUALITIES,
    MODE_LABELS,
    VIDEO_CONTAINERS,
    VIDEO_QUALITIES,
    DownloadOptions,
    Mode,
    audio_label,
    video_label,
)
from .settings import Settings

log = logging.getLogger(LOGGER_NAME)

QUIT_GRACE_SECONDS = 2.0

STATUS_LABELS = {
    State.QUEUED: "⏳ Queued",
    State.FETCHING: "🔎 Fetching info",
    State.DOWNLOADING: "⬇  Downloading",
    State.MERGING: "🔀 Merging…",
    State.CONVERTING: "🎵 Converting…",
    State.FINISHING: "⚙  Finishing…",
    State.DONE: "✅ Done",
    State.FAILED: "❌ Failed",
    State.CANCELLED: "⏹  Cancelled",
}


AUDIO_FORMAT_LABELS = {"original": "Original", "ogg": "ogg (vorbis)"}


def status_label(job: Job) -> str:
    if job.state == State.DOWNLOADING and job.stream:
        return f"⬇  {job.stream.capitalize()}"
    return STATUS_LABELS[job.state]


class JobUpdated(Message):
    def __init__(self, job_id: int):
        super().__init__()
        self.job_id = job_id


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

    #url-input      { width: 3fr; }
    #filename-input { width: 2fr; }
    #path-input     { width: 2fr; }
    #btn-download { width: auto; margin-left: 1; min-width: 14; }

    #options-row { height: auto; align: left middle; }
    #options-row Label { height: 3; content-align: left middle; padding: 0 1 0 2; }
    #mode-select   { width: 22; }
    #format-select { width: 20; }
    #video-select  { width: 14; }
    #audio-select  { width: 14; }

    #download-table { height: 1fr; border: none; background: $surface; }

    #status-bar {
        height: 2;
        padding: 0 2;
        background: $panel;
        border-top: solid $primary;
        content-align: left middle;
        color: $text-muted;
    }
    """

    def __init__(self, log_path: Path | None = None, settings: Settings | None = None):
        super().__init__()
        self.log_path = log_path
        self.settings = settings or Settings(None)
        self.options: DownloadOptions = self.settings.load()
        self.download_counter = 0
        self.jobs: dict[int, Job] = {}
        self.threads: dict[int, threading.Thread] = {}
        self.row_keys: dict[int, object] = {}
        self.highlighted_id: int | None = None
        self._col_keys: dict[str, object] = {}
        self._title_col_width: int = 40

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        o = self.options
        with Vertical(id="top-bar"):
            with Horizontal(id="input-row"):
                yield Input(placeholder="Video URL…", id="url-input")
                yield Input(placeholder="Filename (optional)", id="filename-input")
                yield Input(placeholder="Save path (~/Downloads)", id="path-input")
                yield Button("⬇ Download", variant="primary", id="btn-download")
            with Horizontal(id="options-row"):
                yield Label("Mode")
                modes = [(label, mode) for mode, label in MODE_LABELS.items()]
                yield Select(modes, value=o.mode, allow_blank=False, id="mode-select")
                yield Label("Format")
                yield Select(self._format_choices(o.mode), value=o.format, allow_blank=False, id="format-select")
                yield Label("Video")
                yield Select(
                    [(video_label(q), q) for q in VIDEO_QUALITIES], value=o.video_quality, allow_blank=False,
                    id="video-select",
                )  # fmt: skip
                yield Label("Audio")
                yield Select(
                    [(audio_label(q), q) for q in AUDIO_QUALITIES], value=o.audio_quality, allow_blank=False,
                    id="audio-select",
                )  # fmt: skip
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
        self._sync_option_widgets()

        if not tools.ffmpeg_path():
            message = (
                "ffmpeg not found: downloads will use a single pre-merged file, often lower quality. "
                "Install ffmpeg or use the release build."
            )
            log.warning(message)
            self.notify(message, title="ffmpeg missing", severity="warning", timeout=12)

    def on_resize(self, event: events.Resize) -> None:
        self._resize_title_col()

    def _calc_title_width(self) -> int:
        padding = 2 * self.query_one(DataTable).cell_padding * N_COLS
        return max(12, self.size.width - FIXED_WIDTH - padding - 2)

    def _resize_title_col(self) -> None:
        """Update the Title column width to fill remaining terminal space."""
        if "Title" not in self._col_keys:
            return

        title_w = self._calc_title_width()
        self._title_col_width = title_w

        table = self.query_one(DataTable)
        col_key = self._col_keys["Title"]

        # ── Try to resize the column itself (internal API, version-dependent) ──
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
            for method in ("_clear_caches", "clear_caches", "_invalidate"):
                if hasattr(table, method):
                    try:
                        getattr(table, method)()
                    except Exception:
                        pass

        table.refresh()

        for job_id, job in self.jobs.items():
            try:
                table.update_cell(self.row_keys[job_id], col_key, Text(job.title[:title_w]))
            except CellDoesNotExist:
                pass

    # ── Input events ──────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-download":
            self.start_download()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("url-input", "filename-input", "path-input"):
            self.start_download()

    # ── Download options ──────────────────────────────────────────────────────

    @staticmethod
    def _format_choices(mode: Mode) -> list[tuple[str, str]]:
        if mode == Mode.AUDIO:
            return [(AUDIO_FORMAT_LABELS.get(f, f), f) for f in AUDIO_FORMATS]
        return [(f, f) for f in VIDEO_CONTAINERS]

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is Select.BLANK:
            return
        o = self.options
        match event.select.id:
            case "mode-select":
                changed = replace(o, mode=Mode(event.value))
            case "format-select" if o.mode == Mode.AUDIO:
                changed = replace(o, audio_format=event.value)
            case "format-select":
                changed = replace(o, video_format=event.value)
            case "video-select":
                changed = replace(o, video_quality=event.value)
            case "audio-select":
                changed = replace(o, audio_quality=event.value)
            case _:
                return
        if changed == o:
            return
        mode_changed = changed.mode != o.mode
        self.options = changed
        self.settings.save(changed)
        self._sync_option_widgets(refill_formats=mode_changed)

    def _sync_option_widgets(self, refill_formats: bool = False) -> None:
        o = self.options
        format_select = self.query_one("#format-select", Select)
        with self.prevent(Select.Changed):
            if refill_formats:
                format_select.set_options(self._format_choices(o.mode))
            format_select.value = o.format
        self.query_one("#video-select", Select).disabled = not o.uses_video_quality
        self.query_one("#audio-select", Select).disabled = not o.uses_audio_quality

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        self.highlighted_id = self._job_id(event.row_key)
        if self.highlighted_id is not None:
            self._render_status(self.jobs[self.highlighted_id])

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        job_id = self._job_id(event.row_key)
        if job_id is not None:
            job = self.jobs[job_id]
            self.push_screen(DetailsScreen(job, status_label(job), self.log_path))

    def _job_id(self, row_key) -> int | None:
        value = getattr(row_key, "value", None) or ""
        if value.startswith("dl_") and int(value[3:]) in self.jobs:
            return int(value[3:])
        return None

    # ── Queueing ──────────────────────────────────────────────────────────────

    def start_download(self) -> None:
        url_input = self.query_one("#url-input", Input)
        filename_input = self.query_one("#filename-input", Input)
        path_input = self.query_one("#path-input", Input)

        url = url_input.value.strip()
        custom_name = filename_input.value.strip()
        save_path = path_input.value.strip() or os.path.expanduser("~/Downloads")

        if not url:
            self.notify("Please enter a URL.", severity="warning")
            return

        self.download_counter += 1
        job = Job(
            id=self.download_counter, url=url, save_path=save_path, custom_name=custom_name, options=self.options
        )
        self.jobs[job.id] = job

        table = self.query_one(DataTable)
        self.row_keys[job.id] = table.add_row(
            str(job.id),
            Text(job.title[: self._title_col_width]),
            Text(job.options.label()),
            Text(status_label(job)),
            "—",
            "—",
            "—",
            datetime.now().strftime("%H:%M:%S"),
            key=f"dl_{job.id}",
        )
        table.move_cursor(row=table.get_row_index(self.row_keys[job.id]))
        url_input.clear()
        filename_input.clear()
        log.info("#%d queued %s -> %s [%s]", job.id, url, save_path, job.options.label())

        thread = threading.Thread(
            target=downloader.run, args=(job, self._job_changed), name=f"download-{job.id}", daemon=True
        )
        self.threads[job.id] = thread
        thread.start()

    # ── Worker → UI ───────────────────────────────────────────────────────────

    def _job_changed(self, job: Job) -> None:
        self.post_message(JobUpdated(job.id))

    def on_job_updated(self, message: JobUpdated) -> None:
        job = self.jobs[message.job_id]
        self._render_row(job)
        if job.id == self.highlighted_id:
            self._render_status(job)

    def _render_row(self, job: Job) -> None:
        table = self.query_one(DataTable)
        progress = job.error if job.state == State.FAILED else job.progress
        cells = {
            "Title": job.title[: self._title_col_width],
            "Status": status_label(job),
            "Size": job.size,
            "Progress": progress,
            "ETA": job.eta,
        }
        for column, value in cells.items():
            try:
                table.update_cell(self.row_keys[job.id], self._col_keys[column], Text(value))
            except CellDoesNotExist:
                pass

    def _render_status(self, job: Job) -> None:
        if job.state == State.FAILED:
            hint = f"  ·  Hint: {job.hint}" if job.hint else ""
            line = f"#{job.id}: ❌ {job.error}{hint}   (Enter: details)"
        else:
            line = f"#{job.id}: {status_label(job)}  {job.size}  {job.progress}  ETA {job.eta}"
            if job.warnings:
                line += f"   ⚠ {len(job.warnings)} warning(s) (Enter: details)"
        self.query_one("#status-bar", Static).update(Text(line, no_wrap=True, overflow="ellipsis"))

    # ── Shutdown ──────────────────────────────────────────────────────────────

    async def action_quit(self) -> None:
        active = [job for job in self.jobs.values() if job.state in ACTIVE_STATES]
        for job in active:
            job.cancel.set()
        if active:
            self.notify(f"Stopping {len(active)} active download(s)…")
            await asyncio.to_thread(self._join_workers, QUIT_GRACE_SECONDS)
        self.exit()

    def _join_workers(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        for thread in list(self.threads.values()):
            thread.join(max(0.0, deadline - time.monotonic()))

    def on_unmount(self) -> None:
        for job in self.jobs.values():
            job.cancel.set()
