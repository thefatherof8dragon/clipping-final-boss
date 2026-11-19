"""Video cutting module using FFmpeg."""

import subprocess
from pathlib import Path
from typing import Optional
from .config import find_ffmpeg

def cut_clip(
    source_video: Path,
    output_path: Path,
    start: float,
    end: float,
    accurate: bool = True,
) -> bool:
    """
    Cuts video segment from start to end in seconds and saves to output_path.
    Uses re-encoding for frame accuracy and clean audio/video sync.
    """
    ffmpeg = find_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.5, end - start)

    try:
        if accurate:
            # Re-encode segment for sample-accurate cuts and keyframe alignment
            cmd = [
                ffmpeg,
                "-y",
                "-ss", str(max(0.0, start)),
                "-i", str(source_video),
                "-t", str(duration),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "128k",
                "-avoid_negative_ts", "make_zero",
                "-movflags", "+faststart",
                str(output_path),
            ]
        else:
            # Stream copy (faster, but cuts only on keyframes)
            cmd = [
                ffmpeg,
                "-y",
                "-ss", str(max(0.0, start)),
                "-to", str(end),
                "-i", str(source_video),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                str(output_path),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return output_path.exists() and output_path.stat().st_size > 1000
    except subprocess.CalledProcessError as e:
        print(f"Error cutting clip: {e.stderr}")
        return False
    except Exception as e:
        print(f"Failed to cut clip: {e}")
        return False
