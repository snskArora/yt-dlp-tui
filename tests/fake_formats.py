def _v(fid, ext, vcodec, height, tbr):
    return {"format_id": fid, "ext": ext, "vcodec": vcodec, "acodec": "none", "height": height,
            "width": height * 16 // 9, "tbr": tbr, "vbr": tbr, "url": f"http://x/{fid}", "protocol": "https"}


def _a(fid, ext, acodec, abr):
    return {"format_id": fid, "ext": ext, "vcodec": "none", "acodec": acodec, "abr": abr, "tbr": abr,
            "url": f"http://x/{fid}", "protocol": "https"}


YOUTUBE_LIKE = [
    _v("313", "webm", "vp9", 2160, 12000), _v("401", "mp4", "av01.0.12M.08", 2160, 9000),
    _v("271", "webm", "vp9", 1440, 6000), _v("400", "mp4", "av01.0.08M.08", 1440, 5000),
    _v("137", "mp4", "avc1.640028", 1080, 4000), _v("248", "webm", "vp9", 1080, 2500),
    _v("399", "mp4", "av01.0.08M.08", 1080, 2000),
    _v("136", "mp4", "avc1.4d401f", 720, 2000), _v("247", "webm", "vp9", 720, 1500),
    _v("135", "mp4", "avc1.4d401e", 480, 1000), _v("244", "webm", "vp9", 480, 700),
    _v("134", "mp4", "avc1.4d4015", 360, 500),
    _a("251", "webm", "opus", 160), _a("250", "webm", "opus", 70), _a("249", "webm", "opus", 50),
    _a("140", "m4a", "mp4a.40.2", 128), _a("139", "m4a", "mp4a.40.5", 48),
    {"format_id": "18", "ext": "mp4", "vcodec": "avc1.42001E", "acodec": "mp4a.40.2", "height": 360, "width": 640,
     "tbr": 600, "url": "http://x/18", "protocol": "https"},
]


def info(formats=YOUTUBE_LIKE):
    return {"id": "abc", "title": "t", "extractor": "fake", "extractor_key": "Fake", "webpage_url": "http://x",
            "formats": [dict(f) for f in formats]}
