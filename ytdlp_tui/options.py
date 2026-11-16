from dataclasses import asdict, dataclass, replace
from enum import StrEnum


class Mode(StrEnum):
    AV = "av"
    AUDIO = "audio"
    VIDEO = "video"


MODE_LABELS = {Mode.AV: "Video + audio", Mode.AUDIO: "Audio only", Mode.VIDEO: "Video only"}

VIDEO_CONTAINERS = ("mp4", "mkv", "webm", "mov", "avi", "flv")
AUDIO_FORMATS = ("original", "mp3", "m4a", "opus", "ogg", "flac", "wav", "alac")
LOSSLESS_AUDIO = ("flac", "wav", "alac")
VIDEO_QUALITIES = (0, 2160, 1440, 1080, 720, 480, 360)
AUDIO_QUALITIES = (0, 320, 256, 192, 128, 96)
BEST = 0

CONTAINER_PREFERENCE = {"mp4": ["ext:mp4:m4a"], "webm": ["ext:webm:webm"]}
_H264 = "[vcodec~='^(avc|h264)']"
_MP4_AUDIO = "[acodec~='^(mp4a|aac|mp3)']"
CODEC_FILTERS = {
    "mov": ("[vcodec~='^(avc|h264|hev|hvc|h265)']", _MP4_AUDIO),
    "avi": (_H264, _MP4_AUDIO),
    "flv": (_H264, _MP4_AUDIO),
}
EXTRACT_CODEC = {"original": "best", "ogg": "vorbis"}
SOURCE_PREFERENCE = {"m4a": "aext:m4a", "alac": "aext:m4a", "opus": "aext:webm", "ogg": "aext:ogg", "mp3": "aext:mp3"}
BEST_LOSSY_QUALITY = {"opus": 160}


@dataclass(frozen=True)
class DownloadOptions:
    mode: Mode = Mode.AV
    video_format: str = "mp4"
    audio_format: str = "original"
    video_quality: int = BEST
    audio_quality: int = BEST

    @property
    def format(self) -> str:
        return self.audio_format if self.mode == Mode.AUDIO else self.video_format

    @property
    def uses_video_quality(self) -> bool:
        return self.mode != Mode.AUDIO

    @property
    def uses_audio_quality(self) -> bool:
        if self.mode == Mode.VIDEO:
            return False
        if self.mode == Mode.AUDIO:
            return self.audio_format not in ("original", *LOSSLESS_AUDIO)
        return True

    def label(self) -> str:
        if self.mode == Mode.AUDIO:
            if self.audio_format == "original":
                return "audio orig"
            if self.uses_audio_quality and self.audio_quality:
                return f"{self.audio_format} {self.audio_quality}k"
            return self.audio_format
        quality = f"{self.video_quality}p" if self.video_quality else "best"
        suffix = " mute" if self.mode == Mode.VIDEO else ""
        return f"{self.video_format} {quality}{suffix}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DownloadOptions:
        options = cls()
        try:
            mode = Mode(data.get("mode", options.mode))
        except ValueError:
            mode = options.mode
        checks = {
            "video_format": VIDEO_CONTAINERS,
            "audio_format": AUDIO_FORMATS,
            "video_quality": VIDEO_QUALITIES,
            "audio_quality": AUDIO_QUALITIES,
        }
        values = {k: data[k] for k, allowed in checks.items() if data.get(k) in allowed}
        return replace(options, mode=mode, **values)


def video_label(quality: int) -> str:
    return "Best" if quality == BEST else f"{quality}p"


def audio_label(quality: int) -> str:
    return "Best" if quality == BEST else f"{quality}k"


def _video_sort(options: DownloadOptions) -> list[str]:
    fields = [f"res:{options.video_quality}" if options.video_quality else "res"]
    fields += CONTAINER_PREFERENCE.get(options.video_format, [])
    if options.mode == Mode.AV and options.audio_quality:
        fields.append(f"abr:{options.audio_quality}")
    return fields


def ytdlp_params(options: DownloadOptions, has_ffmpeg: bool) -> dict:
    """yt-dlp params for the chosen options. Container fixing (remux/strip audio) is done by the caller."""
    if options.mode == Mode.AUDIO:
        fields = []
        if pref := SOURCE_PREFERENCE.get(options.audio_format):
            fields.append(pref)
        if options.uses_audio_quality and options.audio_quality:
            fields.append(f"abr:{options.audio_quality}")
        params: dict = {"format": "ba/b", "format_sort": fields}
        if has_ffmpeg:
            quality = None
            if options.uses_audio_quality:
                quality = options.audio_quality or BEST_LOSSY_QUALITY.get(options.audio_format, 0)
            params["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": EXTRACT_CODEC.get(options.audio_format, options.audio_format),
                    "preferredquality": quality,
                }
            ]
        return params

    params = {"format": _video_format(options, has_ffmpeg), "format_sort": _video_sort(options)}
    if has_ffmpeg and options.mode == Mode.AV:
        fmt = options.video_format
        params["merge_output_format"] = fmt if fmt == "mkv" else f"{fmt}/mkv"
    return params


def _video_format(options: DownloadOptions, has_ffmpeg: bool) -> str:
    v, a = CODEC_FILTERS.get(options.video_format, ("", ""))
    if options.mode == Mode.VIDEO:
        chain = [f"bv{v}", "bv", f"b{v}", "b"]
    elif has_ffmpeg:
        chain = [f"bv*{v}+ba{a}", f"bv*{v}+ba", "bv*+ba", "b"]
    else:
        chain = [f"b{v}{a}", f"b{v}", "b"]
    return "/".join(dict.fromkeys(chain))


def ffmpeg_needed_warning(options: DownloadOptions) -> str:
    if options.mode == Mode.AUDIO:
        if options.audio_format == "original":
            return "ffmpeg not found: downloading the best audio stream as is"
        return f"ffmpeg not found: can't convert to {options.audio_format}; downloading the best audio stream as is"
    if options.mode == Mode.VIDEO:
        return "ffmpeg not found: can't remove audio or change container; downloading the best video file as is"
    return "ffmpeg not found: using the best single file (no merging, possibly lower quality), container as is"
