import os


def build_outtmpl(save_path: str, custom_name: str) -> str:
    """Output template for yt-dlp: honor a user-given filename, else fall back to title."""
    if custom_name:
        return os.path.join(save_path, f"{custom_name}.%(ext)s")
    return os.path.join(save_path, "%(title)s.%(ext)s")


def display_name(custom_name: str, fetched_title: str) -> str:
    """"file_name | yt-dlp name" when both are known and differ, else whichever is known."""
    if custom_name and fetched_title and custom_name != fetched_title:
        return f"{custom_name} | {fetched_title}"
    return custom_name or fetched_title
