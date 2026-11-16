"""Build a release bundle: PyInstaller onedir + pinned ffmpeg/ffprobe/deno, then archive (and AppImage on Linux)."""

import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
CACHE = BUILD / "downloads"
APP = "ytdl-tui"

FFMPEG_RELEASE = "https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-10-31-12-59"
FFMPEG_NAME = "ffmpeg-n9.0.2-39-g7adfbe40dc-{platform}-gpl-shared-9.0"
DENO_RELEASE = "https://github.com/denoland/deno/releases/download/v2.9.8"


@dataclass(frozen=True)
class Pinned:
    url: str
    sha256: str

    @property
    def filename(self) -> str:
        return self.url.rsplit("/", 1)[1]


TOOLS = {
    "linux": {
        "ffmpeg": Pinned(
            f"{FFMPEG_RELEASE}/{FFMPEG_NAME.format(platform='linux64')}.tar.xz",
            "90a42a7d9689c031beacc3d03b139fd8243351d616988e8a74188df949fe5d08",
        ),
        "deno": Pinned(
            f"{DENO_RELEASE}/deno-x86_64-unknown-linux-gnu.zip",
            "e890975bc2549807bbcc0b584ffafda72cc7c93349dd99c80483dd784f6c4609",
        ),
    },
    "windows": {
        "ffmpeg": Pinned(
            f"{FFMPEG_RELEASE}/{FFMPEG_NAME.format(platform='win64')}.zip",
            "1d9823c35c7a7e2f54d1438cf61030d6efabe3278de01c191309d1e828bb74df",
        ),
        "deno": Pinned(
            f"{DENO_RELEASE}/deno-x86_64-pc-windows-msvc.zip",
            "cba84b26e0df5ae7f74fc66b86a95b866872a86292ebd84fa1e959927edd93bf",
        ),
    },
}

APPIMAGETOOL = Pinned(
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage",
    "e8c1169c4af66c3184d7ee110713d4be04befe671fa358e2c1591ee840553b03",
)
APPIMAGE_RUNTIME = Pinned(
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
    "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
)


def fetch(pinned: Pinned) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / pinned.filename
    if not path.exists() or sha256(path) != pinned.sha256:
        print(f"download {pinned.url}", file=sys.stderr)
        tmp = path.with_suffix(path.suffix + ".part")
        with urllib.request.urlopen(pinned.url) as response, tmp.open("wb") as out:
            shutil.copyfileobj(response, out)
        tmp.replace(path)
    actual = sha256(path)
    if actual != pinned.sha256:
        sys.exit(f"checksum mismatch for {pinned.filename}: expected {pinned.sha256}, got {actual}")
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unpack(archive: Path) -> Path:
    dest = BUILD / "extract" / archive.name
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
    else:
        with tarfile.open(archive) as t:
            t.extractall(dest, filter="data")
    return dest


def copy(src: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / src.name, follow_symlinks=False)


def install_tools(platform: str, bundle: Path) -> None:
    tools = bundle / "tools"
    shutil.rmtree(tools, ignore_errors=True)
    exe = ".exe" if platform == "windows" else ""

    ffmpeg_root = next(unpack(fetch(TOOLS[platform]["ffmpeg"])).iterdir())
    for name in ("ffmpeg", "ffprobe"):
        copy(ffmpeg_root / "bin" / f"{name}{exe}", tools / "bin")
    if platform == "windows":
        for dll in (ffmpeg_root / "bin").glob("*.dll"):
            copy(dll, tools / "bin")
    else:
        for lib in (ffmpeg_root / "lib").glob("*.so.*"):
            copy(lib, tools / "lib")
    (tools / "licenses").mkdir(parents=True)
    shutil.copy2(ffmpeg_root / "LICENSE.txt", tools / "licenses" / "ffmpeg-LICENSE.txt")

    deno = unpack(fetch(TOOLS[platform]["deno"])) / f"deno{exe}"
    copy(deno, tools / "bin")
    if platform != "windows":
        for binary in (tools / "bin").iterdir():
            binary.chmod(0o755)


def pyinstaller() -> Path:
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", APP,
            "--distpath", str(DIST), "--workpath", str(BUILD / "pyinstaller"), "--specpath", str(BUILD),
            str(ROOT / "main.py"),
        ],
        check=True,
    )  # fmt: skip
    return DIST / APP


def png_icon(size: int = 256, rgb: tuple[int, int, int] = (1, 105, 111)) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    row = b"\x00" + bytes(rgb) * size
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(row * size)) + chunk(b"IEND", b"")


DESKTOP_ENTRY = f"""[Desktop Entry]
Type=Application
Name={APP}
Comment=Personal TUI video downloader
Exec={APP}
Icon={APP}
Terminal=true
Categories=Utility;
"""


def appimage(bundle: Path, output: Path) -> None:
    appdir = BUILD / "AppDir"
    shutil.rmtree(appdir, ignore_errors=True)
    shutil.copytree(bundle, appdir / "usr" / "lib" / APP, symlinks=True)
    (appdir / "AppRun").symlink_to(f"usr/lib/{APP}/{APP}")
    (appdir / f"{APP}.desktop").write_text(DESKTOP_ENTRY)
    (appdir / f"{APP}.png").write_bytes(png_icon())

    tool = fetch(APPIMAGETOOL)
    tool.chmod(0o755)
    runtime = fetch(APPIMAGE_RUNTIME)
    env = {**os.environ, "ARCH": "x86_64", "APPIMAGE_EXTRACT_AND_RUN": "1"}
    subprocess.run([str(tool), "--no-appstream", "--runtime-file", str(runtime), str(appdir), str(output)],
                   check=True, env=env)  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=sorted(TOOLS), default="windows" if os.name == "nt" else "linux")
    parser.add_argument("--no-appimage", action="store_true")
    parser.add_argument("--tools-only", metavar="DIR", help="only install the pinned tools into DIR/tools (for tests)")
    args = parser.parse_args()

    if args.tools_only:
        install_tools(args.platform, Path(args.tools_only).resolve())
        print(Path(args.tools_only).resolve() / "tools" / "bin")
        return

    bundle = pyinstaller()
    install_tools(args.platform, bundle)

    stem = DIST / f"{APP}-{args.platform}-x86_64"
    if args.platform == "windows":
        shutil.make_archive(str(stem), "zip", DIST, APP)
    else:
        with tarfile.open(f"{stem}.tar.gz", "w:gz") as tar:
            tar.add(bundle, arcname=APP)
        if not args.no_appimage:
            appimage(bundle, Path(f"{stem}.AppImage"))
    for artifact in sorted(DIST.glob(f"{APP}-*")):
        print(f"built {artifact.name}  {artifact.stat().st_size / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
