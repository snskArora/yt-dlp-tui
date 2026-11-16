import time

from textual.widgets import DataTable, Select, Static, TextArea

from ytdlp_tui.app import DownloaderApp
from ytdlp_tui.details import DetailsScreen
from ytdlp_tui.downloader import State
from ytdlp_tui.options import DownloadOptions, Mode
from ytdlp_tui.settings import Settings


async def _submit(app, pilot, url: str, folder: str) -> None:
    app.query_one("#url-input").value = url
    app.query_one("#path-input").value = folder
    await pilot.press("enter")


async def _wait_for(pilot, predicate, timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        await pilot.pause(0.05)
    assert predicate()


def _status_text(app) -> str:
    return str(app.query_one("#status-bar", Static).render())


async def test_markup_in_title_and_error_does_not_crash(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/missing/[/bold]/x.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state == State.FAILED)
        await pilot.pause()
        assert "[/bold]" in app.jobs[1].title
        assert "404" in _status_text(app)
        title_cell = app.query_one(DataTable).get_cell(app.row_keys[1], app._col_keys["Title"])
        assert "[/bold]" in str(title_cell)


async def test_done_row_shows_final_size(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/clip.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state == State.DONE)
        await pilot.pause()
        size_cell = app.query_one(DataTable).get_cell(app.row_keys[1], app._col_keys["Size"])
        assert str(size_cell) == app.jobs[1].size != "—"


async def test_status_bar_follows_highlighted_row(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/missing.mp4", str(tmp_path))
        await _submit(app, pilot, f"{http_server}/clip.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state == State.FAILED and app.jobs[2].state == State.DONE)
        await pilot.pause()
        assert _status_text(app).startswith("#2:")
        app.query_one(DataTable).move_cursor(row=0)
        await pilot.pause()
        assert _status_text(app).startswith("#1:") and "404" in _status_text(app)


async def test_enter_opens_details_with_full_error(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/missing.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state == State.FAILED)
        app.query_one(DataTable).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DetailsScreen)
        assert app.jobs[1].error in app.screen.query_one(TextArea).text
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, DetailsScreen)


async def test_quit_cancels_active_downloads(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/slow.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state == State.DOWNLOADING)
        start = time.monotonic()
        await app.action_quit()
        elapsed = time.monotonic() - start
    assert elapsed < 2
    assert app.jobs[1].state == State.CANCELLED
    assert not app.threads[1].is_alive()


async def test_mode_switch_swaps_formats_and_disables_dropdowns(tmp_path):
    app = DownloaderApp(settings=Settings(tmp_path / "settings.json"))
    async with app.run_test(size=(160, 30)) as pilot:
        fmt, video, audio = (app.query_one(f"#{n}-select", Select) for n in ("format", "video", "audio"))
        assert (fmt.value, video.value, audio.value) == ("mp4", 0, 0)
        assert not video.disabled and not audio.disabled

        app.query_one("#mode-select", Select).value = Mode.AUDIO
        await pilot.pause()
        assert fmt.value == "original" and video.disabled and audio.disabled

        fmt.value = "mp3"
        await pilot.pause()
        assert app.options.audio_format == "mp3" and not audio.disabled

        app.query_one("#mode-select", Select).value = Mode.AV
        await pilot.pause()
        assert fmt.value == "mp4" and not video.disabled

        app.query_one("#mode-select", Select).value = Mode.VIDEO
        await pilot.pause()
        assert audio.disabled and not video.disabled


async def test_choices_are_remembered(tmp_path):
    settings = Settings(tmp_path / "settings.json")
    app = DownloaderApp(settings=settings)
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#format-select", Select).value = "mkv"
        app.query_one("#video-select", Select).value = 720
        await pilot.pause()
    assert settings.load() == DownloadOptions(video_format="mkv", video_quality=720)

    app = DownloaderApp(settings=settings)
    async with app.run_test(size=(160, 30)) as pilot:
        assert app.query_one("#format-select", Select).value == "mkv"
        assert app.query_one("#video-select", Select).value == 720


async def test_download_uses_selected_options_and_shows_format(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(160, 30)) as pilot:
        app.query_one("#video-select", Select).value = 1080
        await pilot.pause()
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/clip.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state in (State.DONE, State.FAILED))
        assert app.jobs[1].options == DownloadOptions(video_quality=1080)
        cell = app.query_one(DataTable).get_cell(app.row_keys[1], app._col_keys["Format"])
        assert str(cell) == "mp4 1080p"


async def test_forbidden_shows_hint_in_status_and_details(http_server, tmp_path):
    app = DownloaderApp()
    async with app.run_test(size=(220, 30)) as pilot:
        app.query_one("#url-input").focus()
        await _submit(app, pilot, f"{http_server}/forbidden.mp4", str(tmp_path))
        await _wait_for(pilot, lambda: app.jobs[1].state == State.FAILED)
        await pilot.pause()
        assert "Hint: yt-dlp may be outdated" in _status_text(app)
        app.query_one(DataTable).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert "Hint:\nyt-dlp may be outdated" in app.screen.query_one(TextArea).text
