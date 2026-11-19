"""Shared test fixtures using real sample media."""

import subprocess
import pytest
from pathlib import Path
from clipper.config import find_ffmpeg, DATA_DIR, ensure_directories

@pytest.fixture(scope="session")
def test_video_path(tmp_path_factory) -> Path:
    """Extracts a 10-second real speech video slice into a temporary directory for tests."""
    ensure_directories()
    tmp_dir = tmp_path_factory.mktemp("media")
    video_file = tmp_dir / "real_test_sample.mp4"

    source_real = Path(__file__).resolve().parent.parent / "data" / "real_speech_5min_final.mp4"
    if not source_real.exists():
        raise FileNotFoundError(f"Real test video missing at: {source_real}")

    ffmpeg = find_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-ss", "0.0",
        "-i", str(source_real),
        "-t", "10.0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-avoid_negative_ts", "make_zero",
        str(video_file),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    assert video_file.exists() and video_file.stat().st_size > 5000
    return video_file

@pytest.fixture(scope="session")
def sample_words():
    return [
        {"word": "Wait", "start": 0.5, "end": 0.9, "prob": 0.98},
        {"word": "for", "start": 0.9, "end": 1.2, "prob": 0.99},
        {"word": "it!", "start": 1.2, "end": 1.8, "prob": 0.97},
        {"word": "This", "start": 2.0, "end": 2.3, "prob": 0.95},
        {"word": "is", "start": 2.3, "end": 2.5, "prob": 0.96},
        {"word": "crazy!", "start": 2.5, "end": 3.2, "prob": 0.98},
    ]
