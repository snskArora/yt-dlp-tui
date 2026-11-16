import os

from yt_dlp.postprocessor.ffmpeg import FFmpegPostProcessor, FFmpegPostProcessorError
from yt_dlp.utils import prepend_extension, replace_extension

ANNEXB_FILTERS = {"h264": "h264_mp4toannexb"}
REJECTED = {"avi": {"hevc"}}


class ContainerPP(FFmpegPostProcessor):
    """Remux the finished file into the chosen container without re-encoding; keep its container if impossible."""

    def __init__(self, downloader, target: str, strip_audio: bool):
        super().__init__(downloader)
        self.target = target
        self.strip_audio = strip_audio

    def run(self, info):
        path, ext = info["filepath"], info["ext"]
        streams = self.get_metadata_object(path).get("streams", [])
        vcodec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "video"), None)
        acodec = next((s.get("codec_name") for s in streams if s.get("codec_type") == "audio"), None)
        strip = self.strip_audio and acodec is not None
        if ext == self.target and not strip:
            return [], info

        out, error = None, None
        if vcodec not in REJECTED.get(self.target, ()):
            out, error = self._remux(path, ext, self.target, vcodec, strip)
        if out is None:
            codecs = "/".join(filter(None, (vcodec, None if strip else acodec))) or "these streams"
            reason = f" ({error})" if error else ""
            self.report_warning(f"{codecs} can't go into .{self.target} without re-encoding; kept .{ext}{reason}")
            if not strip:
                return [], info
            out, error = self._remux(path, ext, ext, vcodec, strip)
            if out is None:
                self.report_warning(f"couldn't remove the audio track ({error})")
                return [], info

        target_ext = os.path.splitext(out)[1][1:]
        info["filepath"], info["ext"] = out, target_ext
        return ([path] if out != path else []), info

    def _remux(self, path, ext, target, vcodec, strip) -> tuple[str | None, str | None]:
        out = replace_extension(path, target, ext)
        temp = prepend_extension(out, "temp")
        opts = ["-map", "0:v"] + ([] if strip else ["-map", "0:a?"]) + ["-c", "copy"]
        if target == "avi" and vcodec in ANNEXB_FILTERS:
            opts += ["-bsf:v", ANNEXB_FILTERS[vcodec]]
        self.to_screen(f"Remuxing into {target}{' without audio' if strip else ''}: {out}")
        try:
            self.run_ffmpeg(path, temp, opts)
        except FFmpegPostProcessorError as e:
            if os.path.exists(temp):
                os.remove(temp)
            lines = (e.msg or "").strip().splitlines()
            return None, (lines[-1] if lines else "ffmpeg failed")
        os.replace(temp, out)
        return out, None
