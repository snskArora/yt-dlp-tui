from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from .downloader import Job


class DetailsScreen(ModalScreen[None]):
    BINDINGS = [Binding("escape", "dismiss", "Close")]

    CSS = """
    DetailsScreen { align: center middle; }
    #details {
        width: 90%;
        height: 85%;
        border: thick $primary;
        background: $panel;
        padding: 0 1;
    }
    #details-title { text-style: bold; }
    #details-log { height: 1fr; margin-top: 1; }
    #details-hint { color: $text-muted; }
    """

    def __init__(self, job: Job, status_label: str, log_path: Path | None):
        super().__init__()
        self.job = job
        self.status_label = status_label
        self.log_path = log_path

    def compose(self) -> ComposeResult:
        job = self.job
        summary = [
            f"URL:     {job.url}",
            f"Status:  {self.status_label}",
            f"File:    {job.filepath or '—'}",
            f"Folder:  {job.save_path}",
        ]
        body = []
        if job.error:
            body += ["Error:", job.error, ""]
        if job.hint:
            body += ["Hint:", job.hint, ""]
        if job.warnings:
            body += ["Warnings:", *job.warnings, ""]
        body += ["yt-dlp output:", *(job.log or ["(nothing yet)"])]
        hint = "Esc: close"
        if self.log_path:
            hint += f"  ·  Full log: {self.log_path}"
        with Vertical(id="details"):
            yield Static(Text(f"#{job.id}  {job.title}"), id="details-title")
            yield Static(Text("\n".join(summary)))
            yield TextArea("\n".join(body), read_only=True, soft_wrap=True, id="details-log")
            yield Static(Text(hint), id="details-hint")
