"""
System health and environment safety checks for Clipping Final Boss.
Validates dependencies (FFmpeg, ffprobe, yt-dlp, Python), disk space,
write permissions, and Windows 260-character path limit warnings.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any

from .config import ROOT_DIR, DATA_DIR, find_ffmpeg, find_ffprobe

try:
    import yt_dlp
    YTDLP_VERSION = getattr(yt_dlp, "__version__", getattr(yt_dlp.version, "__version__", "installed"))
except Exception:
    YTDLP_VERSION = None


def get_system_health() -> Dict[str, Any]:
    """
    Performs full environment diagnostic:
    1. FFmpeg & ffprobe presence and versions
    2. yt-dlp presence and version
    3. Python version
    4. Data directory write access & disk capacity
    5. Project path length & Windows MAX_PATH (260 char) safety check
    """
    ffmpeg_bin = find_ffmpeg()
    ffprobe_bin = find_ffprobe()

    ffmpeg_ok = False
    ffmpeg_ver = ""
    if shutil.which(ffmpeg_bin) or (os.path.isabs(ffmpeg_bin) and os.path.exists(ffmpeg_bin)):
        try:
            res = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                ffmpeg_ok = True
                first_line = res.stdout.splitlines()[0] if res.stdout else ""
                ffmpeg_ver = first_line.replace("ffmpeg version", "").strip().split(" ")[0]
        except Exception:
            ffmpeg_ok = True
            ffmpeg_ver = "available"

    ffprobe_ok = False
    ffprobe_ver = ""
    if shutil.which(ffprobe_bin) or (os.path.isabs(ffprobe_bin) and os.path.exists(ffprobe_bin)):
        try:
            res = subprocess.run([ffprobe_bin, "-version"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0:
                ffprobe_ok = True
                first_line = res.stdout.splitlines()[0] if res.stdout else ""
                ffprobe_ver = first_line.replace("ffprobe version", "").strip().split(" ")[0]
        except Exception:
            ffprobe_ok = True
            ffprobe_ver = "available"

    # Disk usage and write access
    data_dir_path = DATA_DIR.resolve()
    writable = False
    try:
        data_dir_path.mkdir(parents=True, exist_ok=True)
        test_file = data_dir_path / ".health_test"
        test_file.write_text("ok", encoding="utf-8")
        writable = test_file.exists()
        test_file.unlink(missing_ok=True)
    except Exception:
        writable = False

    free_gb = 0.0
    total_gb = 0.0
    try:
        usage = shutil.disk_usage(str(data_dir_path))
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
    except Exception:
        pass

    # Windows MAX_PATH (260 char) & Workspace Path Safety
    project_path_str = str(ROOT_DIR.resolve())
    path_len = len(project_path_str)
    path_warning = ""

    is_windows = sys.platform.startswith("win")
    is_temp_or_nested = any(
        sub in project_path_str.lower()
        for sub in ("\\temp", "/temp", "\\tmp", "/tmp", "appdata", ".gemini", "antigravity", "\\brain\\")
    )

    if is_windows and (path_len > 150 or is_temp_or_nested):
        path_warning = (
            f"Path Warning: The project root path is long ({path_len} characters) or in a temporary workspace directory. "
            f"Windows limits file paths to 260 characters, which may cause faster-whisper CTranslate2 libraries or FFmpeg "
            f"subtitle renderers to fail with 'The filename or extension is too long'. "
            f"We strongly recommend moving or cloning the project to a short, permanent folder such as C:\\clipper."
        )

    all_good = bool(ffmpeg_ok and ffprobe_ok and (YTDLP_VERSION is not None) and writable)
    overall_status = "healthy" if (all_good and not path_warning) else ("warning" if all_good else "critical")

    return {
        "status": overall_status,
        "ffmpeg": {
            "present": ffmpeg_ok,
            "version": ffmpeg_ver or "not found",
            "path": ffmpeg_bin,
        },
        "ffprobe": {
            "present": ffprobe_ok,
            "version": ffprobe_ver or "not found",
            "path": ffprobe_bin,
        },
        "yt_dlp": {
            "present": YTDLP_VERSION is not None,
            "version": YTDLP_VERSION or "not installed",
        },
        "python": {
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "executable": sys.executable,
        },
        "data_dir": {
            "path": str(data_dir_path),
            "writable": writable,
            "free_space_gb": free_gb,
            "total_space_gb": total_gb,
        },
        "path_safety": {
            "project_path": project_path_str,
            "path_length": path_len,
            "is_temp_or_nested": is_temp_or_nested,
            "warning": path_warning,
        },
    }
