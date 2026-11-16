from pathlib import Path

from conftest import needs_ffmpeg, probe

from ytdlp_tui import downloader
from ytdlp_tui.downloader import Job, State
from ytdlp_tui.options import DownloadOptions, Mode

pytestmark = needs_ffmpeg


def _download(url: str, folder: Path, options: DownloadOptions) -> Job:
    job = Job(id=1, url=url, save_path=str(folder), options=options)
    downloader.run(job, lambda j: None)
    assert job.state == State.DONE, f"{job.error}\n" + "\n".join(job.log)
    return job


def _only_file(folder: Path) -> Path:
    files = [p for p in folder.iterdir() if p.is_file()]
    assert len(files) == 1, files
    return files[0]


def test_mp4_stays_mp4(http_server, tmp_path):
    job = _download(f"{http_server}/media/h264_aac.mp4", tmp_path, DownloadOptions())
    assert _only_file(tmp_path).suffix == ".mp4" and not job.warnings


def test_remux_into_mkv(http_server, tmp_path):
    job = _download(f"{http_server}/media/h264_aac.mp4", tmp_path, DownloadOptions(video_format="mkv"))
    out = _only_file(tmp_path)
    assert out.suffix == ".mkv" and Path(job.filepath) == out
    assert probe(out) == {"video": "h264", "audio": "aac"}


def test_avi_gets_annexb_filter(http_server, tmp_path):
    _download(f"{http_server}/media/h264_aac.mp4", tmp_path, DownloadOptions(video_format="avi"))
    assert _only_file(tmp_path).suffix == ".avi"


def test_incompatible_container_keeps_original_and_warns(http_server, tmp_path):
    job = _download(f"{http_server}/media/h264_aac.mp4", tmp_path, DownloadOptions(video_format="webm"))
    assert _only_file(tmp_path).suffix == ".mp4"
    assert any("can't go into .webm" in w for w in job.warnings)


def test_vp9_into_mov_keeps_original(http_server, tmp_path):
    job = _download(f"{http_server}/media/vp9_opus.webm", tmp_path, DownloadOptions(video_format="mov"))
    assert _only_file(tmp_path).suffix == ".webm"
    assert job.warnings


def test_video_only_strips_audio(http_server, tmp_path):
    _download(f"{http_server}/media/h264_aac.mp4", tmp_path, DownloadOptions(mode=Mode.VIDEO))
    out = _only_file(tmp_path)
    assert out.suffix == ".mp4" and probe(out) == {"video": "h264"}


def test_video_only_strips_audio_even_if_container_impossible(http_server, tmp_path):
    options = DownloadOptions(mode=Mode.VIDEO, video_format="webm")
    job = _download(f"{http_server}/media/h264_aac.mp4", tmp_path, options)
    out = _only_file(tmp_path)
    assert out.suffix == ".mp4" and probe(out) == {"video": "h264"} and job.warnings


def test_audio_mp3(http_server, tmp_path):
    options = DownloadOptions(mode=Mode.AUDIO, audio_format="mp3", audio_quality=128)
    job = _download(f"{http_server}/media/h264_aac.mp4", tmp_path, options)
    out = _only_file(tmp_path)
    assert out.suffix == ".mp3" and probe(out) == {"audio": "mp3"} and job.size != "—"


def test_audio_original_copies_codec(http_server, tmp_path):
    _download(f"{http_server}/media/h264_aac.mp4", tmp_path, DownloadOptions(mode=Mode.AUDIO))
    out = _only_file(tmp_path)
    assert out.suffix == ".m4a" and probe(out) == {"audio": "aac"}


def test_audio_flac(http_server, tmp_path):
    _download(f"{http_server}/media/vp9_opus.webm", tmp_path, DownloadOptions(mode=Mode.AUDIO, audio_format="flac"))
    out = _only_file(tmp_path)
    assert out.suffix == ".flac" and probe(out) == {"audio": "flac"}
