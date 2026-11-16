import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

import yt_dlp
from yt_dlp.postprocessor.common import PostProcessor
from yt_dlp.utils import DownloadCancelled, DownloadError

from . import tools
from .container import ContainerPP
from .formatting import fmt_duration, fmt_size
from .hints import hint_for
from .logs import LOGGER_NAME
from .naming import build_outtmpl, display_name
from .options import DownloadOptions, Mode, ffmpeg_needed_warning, ytdlp_params

log = logging.getLogger(LOGGER_NAME)

LOG_LINES = 500
PROGRESS_INTERVAL = 0.25


class State(StrEnum):
    QUEUED = "queued"
    FETCHING = "fetching"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    CONVERTING = "converting"
    FINISHING = "finishing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


ACTIVE_STATES = {State.QUEUED, State.FETCHING, State.DOWNLOADING, State.MERGING, State.CONVERTING, State.FINISHING}


@dataclass
class Job:
    id: int
    url: str
    save_path: str
    custom_name: str = ""
    options: DownloadOptions = field(default_factory=DownloadOptions)
    title: str = ""
    state: State = State.QUEUED
    stream: str = ""
    size: str = "—"
    progress: str = "—"
    eta: str = "—"
    error: str = ""
    hint: str = ""
    filepath: str = ""
    log: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cancel: threading.Event = field(default_factory=threading.Event)

    def __post_init__(self):
        if not self.title:
            self.title = self.custom_name or self.url


Notify = Callable[[Job], None]


class _JobLogger:
    def __init__(self, job: Job):
        self.job = job

    def debug(self, msg: str) -> None:
        if not msg.startswith("[debug] "):
            self._add(logging.INFO, msg)

    def info(self, msg: str) -> None:
        self._add(logging.INFO, msg)

    def warning(self, msg: str) -> None:
        self.job.warnings.append(msg)
        self._add(logging.WARNING, msg)

    def error(self, msg: str) -> None:
        self._add(logging.ERROR, msg)

    def _add(self, level: int, msg: str) -> None:
        self.job.log.append(msg)
        del self.job.log[:-LOG_LINES]
        log.log(level, "#%d %s", self.job.id, msg)


class _TitlePP(PostProcessor):
    def __init__(self, job: Job, notify: Notify):
        super().__init__()
        self.job = job
        self.notify = notify

    def run(self, info):
        self.job.title = display_name(self.job.custom_name, info.get("title") or self.job.url)
        self.notify(self.job)
        return [], info


PP_STATES = {"Merger": State.MERGING, "ExtractAudio": State.CONVERTING}


def _stream_label(info: dict) -> str:
    ids = [f.get("format_id") for f in info.get("requested_formats") or []]
    if len(ids) < 2 or info.get("format_id") not in ids:
        return ""
    kind = "audio" if info.get("vcodec") == "none" else "video"
    return f"{kind} {ids.index(info['format_id']) + 1}/{len(ids)}"


def _final_path(info: dict) -> str:
    for item in [info, *(info.get("entries") or [])][::-1]:
        downloads = (item or {}).get("requested_downloads") or []
        if downloads and downloads[-1].get("filepath"):
            return downloads[-1]["filepath"]
    return ""


def _clean_error(msg: str) -> str:
    return msg.removeprefix("ERROR: ").strip()


def run(job: Job, notify: Notify) -> None:
    last_progress = 0.0

    def progress_hook(d: dict) -> None:
        nonlocal last_progress
        if job.cancel.is_set():
            raise DownloadCancelled()
        if d["status"] != "downloading":
            return
        now = time.monotonic()
        if now - last_progress < PROGRESS_INTERVAL and job.state == State.DOWNLOADING:
            return
        last_progress = now
        done = d.get("downloaded_bytes")
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        speed = d.get("speed")
        percent = f"{done / total * 100:.1f}%" if done is not None and total else "?"
        job.state = State.DOWNLOADING
        job.stream = _stream_label(d.get("info_dict") or {})
        job.size = f"{fmt_size(done)} / {fmt_size(total)}"
        job.progress = f"{percent} @ {fmt_size(speed)}/s" if speed else percent
        job.eta = fmt_duration(d.get("eta"))
        notify(job)

    def postprocessor_hook(d: dict) -> None:
        if d["status"] == "started":
            job.state = PP_STATES.get(d.get("postprocessor"), State.FINISHING)
            job.stream = ""
            notify(job)

    logger = _JobLogger(job)
    has_ffmpeg = tools.ffmpeg_path() is not None
    if not has_ffmpeg:
        logger.warning(ffmpeg_needed_warning(job.options))

    opts = {
        **ytdlp_params(job.options, has_ffmpeg),
        "outtmpl": build_outtmpl(job.save_path, job.custom_name),
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
        "logger": logger,
        "quiet": True,
        "noprogress": True,
        "color": {"stdout": "no_color", "stderr": "no_color"},
        **tools.ytdlp_tool_opts(),
    }

    try:
        if job.cancel.is_set():
            raise DownloadCancelled()
        job.state = State.FETCHING
        notify(job)
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.add_post_processor(_TitlePP(job, notify), when="pre_process")
            if has_ffmpeg and job.options.mode != Mode.AUDIO:
                strip = job.options.mode == Mode.VIDEO
                ydl.add_post_processor(ContainerPP(ydl, job.options.video_format, strip), when="post_process")
            info = ydl.extract_info(job.url, download=True)
        job.filepath = _final_path(info or {})
        size = os.path.getsize(job.filepath) if job.filepath and os.path.exists(job.filepath) else None
        job.state = State.DONE
        job.size, job.progress, job.eta, job.stream = fmt_size(size), "100%", "—", ""
    except DownloadCancelled:
        job.state = State.CANCELLED
    except DownloadError as e:
        if job.cancel.is_set():
            job.state = State.CANCELLED
        else:
            job.state = State.FAILED
            job.error = _clean_error(e.msg or str(e))
            job.hint = hint_for(job.error)
    except Exception as e:
        log.exception("#%d unexpected error", job.id)
        job.state = State.FAILED
        job.error = f"{type(e).__name__}: {e}"
    if job.state in (State.CANCELLED, State.FAILED):
        job.eta, job.stream = "—", ""
        logger.info(f"download {job.state}")
    notify(job)
