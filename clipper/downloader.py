"""Downloader module supporting yt-dlp URLs and local video files."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
from .config import DATA_IN_DIR, find_ffmpeg, find_ffprobe, settings

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

def get_media_info(file_path: Path) -> Dict[str, Any]:
    """Probe local media file using ffprobe or ffmpeg."""
    ffprobe = find_ffprobe()
    try:
        cmd = [
            ffprobe,
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate:stream=width,height,codec_type",
            "-of", "default=noprint_wrappers=1",
            str(file_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = {}
        for line in result.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                info[k.strip()] = v.strip()
        duration = float(info.get("duration", 0.0))
        width = int(info.get("width", 1280)) if "width" in info else 1280
        height = int(info.get("height", 720)) if "height" in info else 720
        return {
            "duration": duration,
            "width": width,
            "height": height,
        }
    except Exception:
        return {"duration": 30.0, "width": 1280, "height": 720}

def download_or_load(source: str, session_id: str) -> Dict[str, Any]:
    """
    Downloads media from URL using yt-dlp or loads local file.
    Saves to data/in/<session_id>_source.mp4.
    Fails loudly on invalid URLs or download errors. Never reuses stale files.
    """
    src_clean = source.strip()
    src_lower = src_clean.lower()

    # Reject URLs pointing to localhost / 127.0.0.1
    if "localhost" in src_lower or "127.0.0.1" in src_lower or "0.0.0.0" in src_lower:
        raise ValueError("Invalid URL: Cannot download from local server address (localhost / 127.0.0.1).")

    dest_path = DATA_IN_DIR / f"{session_id}_source.mp4"

    # Always clean up any previous file with this session prefix before starting
    for old_f in DATA_IN_DIR.glob(f"{session_id}_source.*"):
        try:
            old_f.unlink()
        except Exception:
            pass

    # Check if source is a local file
    local_path = Path(src_clean)
    if local_path.is_file():
        shutil.copy2(local_path, dest_path)
        info = get_media_info(dest_path)
        if info["duration"] <= 0:
            raise RuntimeError(f"Local file has invalid duration: {local_path}")
        return {
            "file_path": dest_path,
            "title": local_path.stem.replace("_", " ").title(),
            "duration": info["duration"],
            "uploader": "Local File",
            "thumbnail_url": "",
            "is_local": True,
        }

    # Otherwise treat as remote URL via yt-dlp
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed in the environment.")

    ydl_opts = {
        "format": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
        "outtmpl": str(dest_path.with_suffix(".%(ext)s")),
        "overwrites": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

    # Automatically enable Node JS runtime for YouTube challenges
    js_runtime = getattr(settings, "ytdlp_js_runtime", "node")
    if js_runtime and shutil.which(js_runtime):
        ydl_opts["js_runtimes"] = {js_runtime: {}}

    # Optional browser cookies configured in settings
    cookie_browser = getattr(settings, "ytdlp_cookie_browser", "")
    if cookie_browser:
        ydl_opts["cookiesfrombrowser"] = (cookie_browser,)

    # Optional sleep interval between requests
    sleep_interval = getattr(settings, "ytdlp_sleep_interval", 0)
    if sleep_interval > 0:
        ydl_opts["sleep_interval_requests"] = sleep_interval

    # Optional player client configuration
    player_client = getattr(settings, "ytdlp_player_client", "web,android")
    if player_client:
        ydl_opts["extractor_args"] = {"youtube": {"player_client": [c.strip() for c in player_client.split(",")]}}

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            meta = ydl.extract_info(src_clean, download=True)
            if not meta:
                raise RuntimeError("yt-dlp returned empty metadata.")
            title = meta.get("title", "Source Video")
            duration = float(meta.get("duration", 0) or 0)
            uploader = meta.get("uploader", "Unknown Channel")
            thumbnail = meta.get("thumbnail", "")
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "too many requests" in err_str.lower():
            raise RuntimeError(
                f"YouTube HTTP 429 Too Many Requests: YouTube is rate-limiting this IP: wait or enable browser cookies in Settings. (yt-dlp: {err_str})"
            ) from e
        if "bot" in err_str.lower() or "confirm you’re not a bot" in err_str.lower():
            raise RuntimeError(
                f"YouTube anti-bot verification required: try again or enable browser cookies in Settings. (yt-dlp: {err_str})"
            ) from e
        if "unavailable" in err_str.lower():
            raise RuntimeError(
                f"YouTube video is unavailable or private: verify video URL and case-sensitive ID. (yt-dlp: {err_str})"
            ) from e
        if "403" in err_str:
            raise RuntimeError(
                f"YouTube HTTP 403 Forbidden: Request was blocked by YouTube. (yt-dlp: {err_str})"
            ) from e
        raise RuntimeError(f"Download failed: {err_str}") from e

    # Ensure dest_path was produced
    if not dest_path.exists():
        # Check if extension changed
        possible = list(DATA_IN_DIR.glob(f"{session_id}_source.*"))
        if possible and possible[0].is_file() and possible[0].stat().st_size > 5000:
            dest_path = possible[0]
        else:
            raise RuntimeError("Downloaded media file was not created by yt-dlp.")

    if dest_path.stat().st_size < 5000:
        raise RuntimeError(f"Downloaded video file is corrupt or empty ({dest_path.stat().st_size} bytes).")

    if duration == 0:
        duration = get_media_info(dest_path)["duration"]

    if duration <= 0:
        raise RuntimeError("Could not determine valid duration for downloaded video.")

    return {
        "file_path": dest_path,
        "title": title,
        "duration": duration,
        "uploader": uploader,
        "thumbnail_url": thumbnail,
        "is_local": False,
    }
