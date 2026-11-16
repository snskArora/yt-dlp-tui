import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

PAYLOAD = bytes(range(256)) * 4096
MEDIA_TYPES = {".mp4": "video/mp4", ".webm": "video/webm"}
HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg/ffprobe not installed")


class _Handler(BaseHTTPRequestHandler):
    media_dir: Path | None = None

    def log_message(self, *args):
        pass

    def do_HEAD(self):
        self._serve(body=False)

    def do_GET(self):
        self._serve(body=True)

    def _serve(self, body: bool):
        if self.path.startswith("/missing"):
            self.send_error(404)
            return
        if self.path.startswith("/forbidden"):
            self.send_error(403)
            return
        content_type, data = "video/mp4", PAYLOAD
        if self.path.startswith("/media/") and self.media_dir:
            file = self.media_dir / self.path.removeprefix("/media/")
            if not file.is_file():
                self.send_error(404)
                return
            content_type, data = MEDIA_TYPES.get(file.suffix, "application/octet-stream"), file.read_bytes()
        slow = self.path.startswith("/slow")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if not body:
            return
        chunk = 1024 if slow else len(data)
        try:
            for i in range(0, len(data), chunk):
                self.wfile.write(data[i : i + chunk])
                if slow:
                    time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass


def _make_media(folder: Path) -> None:
    src = ["-f", "lavfi", "-i", "testsrc=duration=1:size=128x96:rate=10", "-f", "lavfi", "-i", "sine=duration=1"]
    outputs = {
        "h264_aac.mp4": ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"],
        "vp9_opus.webm": ["-c:v", "libvpx-vp9", "-c:a", "libopus"],
    }
    for name, codecs in outputs.items():
        cmd = ["ffmpeg", "-loglevel", "error", "-y", *src, *codecs, "-shortest", str(folder / name)]
        subprocess.run(cmd, check=True)


@pytest.fixture(scope="session")
def http_server(tmp_path_factory):
    if HAS_FFMPEG:
        media = tmp_path_factory.mktemp("media")
        _make_media(media)
        _Handler.media_dir = media
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def probe(path: Path) -> dict[str, str]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return {kind: codec for codec, kind in (line.split(",") for line in out.stdout.split())}
