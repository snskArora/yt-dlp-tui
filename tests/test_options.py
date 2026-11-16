import json

import pytest
import yt_dlp
from fake_formats import YOUTUBE_LIKE, info

from ytdlp_tui.options import (
    AUDIO_FORMATS,
    VIDEO_CONTAINERS,
    DownloadOptions,
    Mode,
    ytdlp_params,
)
from ytdlp_tui.settings import Settings


def pick(options: DownloadOptions, has_ffmpeg: bool = True, formats=YOUTUBE_LIKE) -> str:
    params = ytdlp_params(options, has_ffmpeg)
    params.pop("postprocessors", None)
    with yt_dlp.YoutubeDL({"quiet": True, "simulate": True, **params}) as ydl:
        return ydl.process_ie_result(info(formats), download=False)["format_id"]


def test_default_is_best_video_mp4():
    o = DownloadOptions()
    assert (o.mode, o.video_format, o.video_quality, o.audio_quality) == (Mode.AV, "mp4", 0, 0)
    assert o.label() == "mp4 best"


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (DownloadOptions(), "401+140"),
        (DownloadOptions(video_format="mkv"), "401+251"),
        (DownloadOptions(video_format="webm"), "313+251"),
        (DownloadOptions(video_quality=1080), "399+140"),
        (DownloadOptions(video_quality=720, video_format="mkv"), "247+251"),
        (DownloadOptions(video_quality=1080, audio_quality=96), "399+139"),
        (DownloadOptions(video_format="mov"), "137+140"),
        (DownloadOptions(video_format="avi"), "137+140"),
        (DownloadOptions(video_format="flv", video_quality=720), "136+140"),
        (DownloadOptions(mode=Mode.VIDEO, video_quality=480), "135"),
        (DownloadOptions(mode=Mode.AUDIO), "251"),
        (DownloadOptions(mode=Mode.AUDIO, audio_format="m4a"), "140"),
        (DownloadOptions(mode=Mode.AUDIO, audio_format="opus", audio_quality=96), "250"),
        (DownloadOptions(mode=Mode.AUDIO, audio_format="mp3", audio_quality=320), "251"),
    ],
    ids=lambda v: v.label() if isinstance(v, DownloadOptions) else v,
)
def test_stream_selection(options, expected):
    assert pick(options) == expected


def test_quality_falls_back_to_smallest_above():
    only_hd = [f for f in YOUTUBE_LIKE if f["vcodec"] == "none" or (f.get("height") or 0) >= 1080]
    assert pick(DownloadOptions(video_quality=360), formats=only_hd) == "399+140"


def test_legacy_container_falls_back_when_nothing_compatible():
    vp9_only = [f for f in YOUTUBE_LIKE if f["vcodec"] in ("vp9", "none")]
    assert pick(DownloadOptions(video_format="mov"), formats=vp9_only) == "313+251"


def test_without_ffmpeg_only_single_files():
    assert pick(DownloadOptions(video_quality=1080), has_ffmpeg=False) == "18"
    params = ytdlp_params(DownloadOptions(mode=Mode.AUDIO, audio_format="mp3"), has_ffmpeg=False)
    assert "postprocessors" not in params


def test_audio_conversion_params():
    pp = ytdlp_params(DownloadOptions(mode=Mode.AUDIO, audio_format="mp3", audio_quality=192), True)["postprocessors"]
    assert pp == [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": 192}]
    pp = ytdlp_params(DownloadOptions(mode=Mode.AUDIO, audio_format="ogg"), True)["postprocessors"][0]
    assert (pp["preferredcodec"], pp["preferredquality"]) == ("vorbis", 0)
    pp = ytdlp_params(DownloadOptions(mode=Mode.AUDIO, audio_format="flac", audio_quality=96), True)["postprocessors"]
    assert pp[0]["preferredquality"] is None
    pp = ytdlp_params(DownloadOptions(mode=Mode.AUDIO, audio_format="original", audio_quality=96), True)
    assert pp["postprocessors"][0]["preferredcodec"] == "best" and pp["format_sort"] == []


def test_merge_prefers_chosen_container_then_mkv():
    assert ytdlp_params(DownloadOptions(video_format="webm"), True)["merge_output_format"] == "webm/mkv"
    assert ytdlp_params(DownloadOptions(video_format="mkv"), True)["merge_output_format"] == "mkv"


def test_which_quality_dropdowns_apply():
    assert not DownloadOptions(mode=Mode.AUDIO).uses_video_quality
    assert not DownloadOptions(mode=Mode.VIDEO).uses_audio_quality
    assert DownloadOptions(mode=Mode.AV).uses_audio_quality
    for fmt, applies in [("original", False), ("flac", False), ("wav", False), ("alac", False), ("mp3", True)]:
        assert DownloadOptions(mode=Mode.AUDIO, audio_format=fmt).uses_audio_quality is applies


def test_labels_fit_column():
    labels = [
        DownloadOptions(mode=m, video_format=f, video_quality=1440).label() for m in Mode for f in VIDEO_CONTAINERS
    ]
    labels += [DownloadOptions(mode=Mode.AUDIO, audio_format=f, audio_quality=320).label() for f in AUDIO_FORMATS]
    assert max(map(len, labels)) <= 15
    assert DownloadOptions(mode=Mode.AUDIO, audio_format="mp3", audio_quality=320).label() == "mp3 320k"
    assert DownloadOptions(mode=Mode.VIDEO, video_quality=720).label() == "mp4 720p mute"


def test_settings_round_trip(tmp_path):
    settings = Settings(tmp_path / "cfg" / "settings.json")
    assert settings.load() == DownloadOptions()
    chosen = DownloadOptions(mode=Mode.AUDIO, audio_format="flac", video_format="mkv", video_quality=720)
    settings.save(chosen)
    assert settings.load() == chosen


def test_settings_ignore_bad_values(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"download": {"mode": "nope", "video_format": "exe", "video_quality": 1080}}))
    assert Settings(path).load() == DownloadOptions(video_quality=1080)
    path.write_text("{not json")
    assert Settings(path).load() == DownloadOptions()
