import json
import logging
import os
import sys
from pathlib import Path

from .logs import APP_NAME, LOGGER_NAME
from .options import DownloadOptions

log = logging.getLogger(LOGGER_NAME)


def default_settings_path() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME / "settings.json"


class Settings:
    def __init__(self, path: Path | None):
        self.path = path

    def load(self) -> DownloadOptions:
        if not self.path:
            return DownloadOptions()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return DownloadOptions.from_dict(data.get("download") or {})
        except FileNotFoundError:
            return DownloadOptions()
        except (OSError, ValueError, AttributeError) as e:
            log.warning("ignoring unreadable settings file %s: %s", self.path, e)
            return DownloadOptions()

    def save(self, options: DownloadOptions) -> None:
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps({"download": options.to_dict()}, indent=2), encoding="utf-8")
            os.replace(temp, self.path)
        except OSError as e:
            log.warning("couldn't save settings to %s: %s", self.path, e)
