"""
System health and environment safety checks for Clipping Final Boss.
Validates dependencies (FFmpeg, ffprobe, yt-dlp, Python, JS runtime), disk space,
write permissions, and Windows path limit warnings.
"""

import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from . import __version__
from .config import ROOT_DIR, DATA_DIR, find_ffmpeg, find_ffprobe

try:
    import yt_dlp
    YTDLP_VERSION = getattr(yt_dlp, "__version__", getattr(yt_dlp.version, "__version__", "installed"))
except Exception:
    YTDLP_VERSION = None

# In-memory cache for static binary version checks to guarantee sub-millisecond response
_CACHED_HEALTH_BINARIES: Dict[str, Any] = {}
_LAST_BINARY_CHECK_TS: float = 0.0

def _get_cached_binaries(force_refresh: bool = False) -> Dict[str, Any]:
    global _CACHED_HEALTH_BINARIES, _LAST_BINARY_CHECK_TS
    now = time.time()
    curr_ffmpeg = find_ffmpeg()
    curr_ffprobe = find_ffprobe()
    if (
        not force_refresh
        and _CACHED_HEALTH_BINARIES
        and (now - _LAST_BINARY_CHECK_TS < 180.0)
        and _CACHED_HEALTH_BINARIES.get("ffmpeg", {}).get("bin") == curr_ffmpeg
        and _CACHED_HEALTH_BINARIES.get("ffprobe", {}).get("bin") == curr_ffprobe
    ):
        return _CACHED_HEALTH_BINARIES

    ffmpeg_bin = curr_ffmpeg
    ffmpeg_ok = False
    ffmpeg_ver = ""
    if shutil.which(ffmpeg_bin) or (os.path.isabs(ffmpeg_bin) and os.path.exists(ffmpeg_bin)):
        try:
            res = subprocess.run([ffmpeg_bin, "-version"], capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                ffmpeg_ok = True
                first_line = res.stdout.splitlines()[0] if res.stdout else ""
                ffmpeg_ver = first_line.replace("ffmpeg version", "").strip().split(" ")[0]
        except Exception:
            ffmpeg_ok = True
            ffmpeg_ver = "available"

    ffprobe_bin = find_ffprobe()
    ffprobe_ok = False
    ffprobe_ver = ""
    if shutil.which(ffprobe_bin) or (os.path.isabs(ffprobe_bin) and os.path.exists(ffprobe_bin)):
        try:
            res = subprocess.run([ffprobe_bin, "-version"], capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                ffprobe_ok = True
                first_line = res.stdout.splitlines()[0] if res.stdout else ""
                ffprobe_ver = first_line.replace("ffprobe version", "").strip().split(" ")[0]
        except Exception:
            ffprobe_ok = True
            ffprobe_ver = "available"

    js_info = check_js_runtime()

    _CACHED_HEALTH_BINARIES = {
        "ffmpeg": {"bin": ffmpeg_bin, "ok": ffmpeg_ok, "ver": ffmpeg_ver},
        "ffprobe": {"bin": ffprobe_bin, "ok": ffprobe_ok, "ver": ffprobe_ver},
        "js": js_info,
    }
    _LAST_BINARY_CHECK_TS = now
    return _CACHED_HEALTH_BINARIES


def check_js_runtime() -> Dict[str, Any]:
    """Check for Deno or Node.js runtime presence and version."""
    for bin_name in ["deno", "node"]:
        p = shutil.which(bin_name)
        if p:
            try:
                res = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=2.0)
                if res.returncode == 0:
                    ver = res.stdout.strip().splitlines()[0]
                    return {"found": True, "runtime": bin_name, "version": ver, "path": p}
            except Exception:
                return {"found": True, "runtime": bin_name, "version": "available", "path": p}
    return {"found": False, "runtime": None, "version": None, "path": None}


def get_system_health() -> Dict[str, Any]:
    """
    Performs full environment diagnostic matching /healthz specification:
    - status ('ok' or 'degraded')
    - app version
    - python version
    - ffmpeg + ffprobe found and version
    - yt-dlp version
    - JS runtime found
    - free disk space in the data folder
    - data folder writable (real write test)
    - project path length (warn if over 100)
    - time (ISO 8601 UTC)
    - failing list (for 503 status code decision)
    """
    failing: List[str] = []

    # Get cached or fresh binary checks (sub-millisecond when cached)
    cached = _get_cached_binaries()
    ffmpeg_bin = cached["ffmpeg"]["bin"]
    ffmpeg_ok = cached["ffmpeg"]["ok"]
    ffmpeg_ver = cached["ffmpeg"]["ver"]
    if not ffmpeg_ok:
        failing.append("ffmpeg missing or unexecutable")

    ffprobe_bin = cached["ffprobe"]["bin"]
    ffprobe_ok = cached["ffprobe"]["ok"]
    ffprobe_ver = cached["ffprobe"]["ver"]
    if not ffprobe_ok:
        failing.append("ffprobe missing or unexecutable")

    # 3. yt-dlp
    if not YTDLP_VERSION:
        failing.append("yt-dlp missing or unimportable")

    # 4. JS Runtime (Node or Deno)
    js_info = cached["js"]
    if not js_info["found"]:
        failing.append("JS runtime (Deno or Node) not found in PATH")

    # 5. Data directory write access & disk capacity
    data_dir_path = DATA_DIR.resolve()
    writable = False
    try:
        data_dir_path.mkdir(parents=True, exist_ok=True)
        test_file = data_dir_path / f".health_test_{int(time.time()*1000)}"
        test_file.write_text("ok", encoding="utf-8")
        writable = test_file.exists() and test_file.read_text(encoding="utf-8") == "ok"
        test_file.unlink(missing_ok=True)
    except Exception:
        writable = False
    if not writable:
        failing.append(f"data folder is not writable: {data_dir_path}")

    free_gb = 0.0
    total_gb = 0.0
    try:
        usage = shutil.disk_usage(str(data_dir_path))
        free_gb = round(usage.free / (1024 ** 3), 2)
        total_gb = round(usage.total / (1024 ** 3), 2)
    except Exception:
        pass

    # 6. Project path length & warning (warn if > 100 characters)
    project_path_str = str(ROOT_DIR.resolve())
    path_len = len(project_path_str)
    path_warning = ""
    is_windows = sys.platform.startswith("win")
    is_temp_or_nested = any(
        sub in project_path_str.lower()
        for sub in ("\\temp", "/temp", "\\tmp", "/tmp", "appdata", ".gemini", "antigravity", "\\brain\\")
    )
    if path_len > 100 or is_temp_or_nested:
        path_warning = (
            f"Path Warning: The project root path length is {path_len} characters "
            f"(warning threshold: 100). Windows MAX_PATH is 260 characters. "
            f"Consider moving project to a short root directory such as C:\\clipper."
        )

    all_required_pass = len(failing) == 0
    status_str = "ok" if (all_required_pass and not path_warning) else ("degraded" if all_required_pass else "failing")

    return {
        "status": status_str,
        "healthy": all_required_pass,
        "app_version": __version__,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "ffmpeg": {
            "found": ffmpeg_ok,
            "present": ffmpeg_ok,
            "version": ffmpeg_ver or "not found",
            "path": ffmpeg_bin,
        },
        "ffprobe": {
            "found": ffprobe_ok,
            "present": ffprobe_ok,
            "version": ffprobe_ver or "not found",
            "path": ffprobe_bin,
        },
        "yt_dlp_version": YTDLP_VERSION or "not installed",
        "yt_dlp": {
            "present": bool(YTDLP_VERSION),
            "version": YTDLP_VERSION or "not installed",
        },
        "python": {
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
        "js_runtime": js_info,
        "data_folder": {
            "path": str(data_dir_path),
            "writable": writable,
            "free_space_gb": free_gb,
            "total_space_gb": total_gb,
        },
        "data_dir": {
            "path": str(data_dir_path),
            "writable": writable,
            "free_space_gb": free_gb,
            "total_space_gb": total_gb,
        },
        "project_path": {
            "path": project_path_str,
            "length": path_len,
            "warning": path_warning,
        },
        "path_safety": {
            "path_length": path_len,
            "project_path": project_path_str,
            "warning": path_warning,
        },
        "time": datetime.now(timezone.utc).isoformat(),
        "failing": failing,
    }
