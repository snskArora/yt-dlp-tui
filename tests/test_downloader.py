import threading
import time

import yt_dlp
from conftest import PAYLOAD

from ytdlp_tui import downloader, tools
from ytdlp_tui.downloader import Job, State
from ytdlp_tui.formatting import fmt_size


def _run(job: Job) -> list[State]:
    states: list[State] = []
    downloader.run(job, lambda j: states.append(j.state))
    return states


def test_download_reports_final_size_and_path(http_server, tmp_path):
    job = Job(id=1, url=f"{http_server}/clip.mp4", save_path=str(tmp_path))
    states = _run(job)
    assert job.state == State.DONE, job.error
    assert job.filepath and (tmp_path / "clip.mp4").samefile(job.filepath)
    assert job.size == fmt_size(len(PAYLOAD))
    assert job.title == "clip"
    assert states[0] == State.FETCHING and states[-1] == State.DONE


def test_custom_name_is_used_for_file_and_title(http_server, tmp_path):
    job = Job(id=1, url=f"{http_server}/clip.mp4", save_path=str(tmp_path), custom_name="mine")
    _run(job)
    assert job.state == State.DONE, job.error
    assert (tmp_path / "mine.mp4").exists()
    assert job.title == "mine | clip"


def test_url_is_extracted_once(http_server, tmp_path, monkeypatch):
    calls = []
    original = yt_dlp.YoutubeDL.extract_info

    def counting(self, *args, **kwargs):
        calls.append(args)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(yt_dlp.YoutubeDL, "extract_info", counting)
    job = Job(id=1, url=f"{http_server}/clip.mp4", save_path=str(tmp_path))
    _run(job)
    assert job.state == State.DONE, job.error
    assert len(calls) == 1


def test_missing_ffmpeg_still_downloads_and_warns(http_server, tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "ffmpeg_path", lambda: None)
    job = Job(id=1, url=f"{http_server}/clip.mp4", save_path=str(tmp_path))
    _run(job)
    assert job.state == State.DONE, job.error
    assert any("ffmpeg not found" in line for line in job.log)


def test_failure_keeps_full_error(http_server, tmp_path):
    job = Job(id=1, url=f"{http_server}/missing.mp4", save_path=str(tmp_path))
    _run(job)
    assert job.state == State.FAILED
    assert "404" in job.error
    assert not job.error.startswith("ERROR:")
    assert len(job.error) > 40
    assert any("404" in line for line in job.log)


def test_cancel_stops_running_download(http_server, tmp_path):
    job = Job(id=1, url=f"{http_server}/slow.mp4", save_path=str(tmp_path))
    thread = threading.Thread(target=_run, args=(job,), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while job.state != State.DOWNLOADING and time.monotonic() < deadline:
        time.sleep(0.02)
    job.cancel.set()
    thread.join(5)
    assert not thread.is_alive()
    assert job.state == State.CANCELLED


def test_cancel_before_start(tmp_path):
    job = Job(id=1, url="http://127.0.0.1:9/never", save_path=str(tmp_path))
    job.cancel.set()
    _run(job)
    assert job.state == State.CANCELLED


def test_forbidden_gets_outdated_hint(http_server, tmp_path):
    job = Job(id=1, url=f"{http_server}/forbidden.mp4", save_path=str(tmp_path))
    _run(job)
    assert job.state == State.FAILED and "403" in job.error
    assert "yt-dlp may be outdated" in job.hint and "uv lock --upgrade-package yt-dlp" in job.hint


def test_other_errors_get_no_hint(http_server, tmp_path):
    job = Job(id=1, url=f"{http_server}/missing.mp4", save_path=str(tmp_path))
    _run(job)
    assert job.state == State.FAILED and job.hint == ""


def test_hint_mentions_release_when_frozen(monkeypatch):
    import sys

    from ytdlp_tui.hints import hint_for

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert "newest ytdl-tui release" in hint_for("ERROR: HTTP Error 403: Forbidden")
