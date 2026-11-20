"""Unit tests for multi-platform social export packaging."""

import pytest
import json
from pathlib import Path
from fastapi import HTTPException
from clipper.api import api_export_clip_package
from clipper.config import DATA_OUT_DIR

@pytest.fixture
def mock_session_clip(tmp_path, monkeypatch):
    """Creates a temporary session directory and mock clip in session.json."""
    sess_dir = DATA_OUT_DIR / "session_test_export"
    sess_dir.mkdir(parents=True, exist_ok=True)
    fake_video = sess_dir / "01_clip.mp4"
    fake_video.write_text("fake video data", encoding="utf-8")

    clip = {
        "id": "clip_1",
        "rank": 1,
        "title": "Unbelievable Victory Moment",
        "hook_text": "WAIT FOR THE END?!",
        "caption": "Streamer executes a flawless game-winning maneuver in the final seconds.",
        "hashtags": ["#gaming", "#clutch", "#viral", "#win"],
        "duration": 24.5,
        "file_path": str(fake_video),
        "transcript_text": "Wait for the end, this is crazy! He got the victory.",
    }

    session_data = {
        "session_id": "session_test_export",
        "clips": [clip],
    }
    (sess_dir / "session.json").write_text(json.dumps(session_data), encoding="utf-8")

    yield "session_test_export:clip_1"

    # Cleanup
    try:
        import shutil
        if sess_dir.exists():
            shutil.rmtree(sess_dir, ignore_errors=True)
    except Exception:
        pass

def test_youtube_shorts_export(mock_session_clip):
    """Verify YouTube Shorts export package formatting."""
    res = api_export_clip_package(mock_session_clip, "youtube_shorts")
    assert res["platform"] == "youtube_shorts"
    assert "#shorts" in res["title"].lower()
    assert len(res["title"]) <= 100
    assert "gaming" in res["tags"]
    assert "clutch" in res["tags"]
    assert "#" not in res["tags"][0]
    assert "tags_string" in res
    assert "formatted_text" in res
    assert res["title"] in res["formatted_text"]
    assert res["video_path"] != ""

def test_instagram_reels_export(mock_session_clip):
    """Verify Instagram Reels export package formatting."""
    res = api_export_clip_package(mock_session_clip, "instagram_reels")
    assert res["platform"] == "instagram_reels"
    assert "WAIT FOR THE END?!" in res["hook"]
    assert "#reels" in res["hashtags"]
    assert len(res["formatted_text"]) <= 2200
    assert ".\n.\n" in res["formatted_text"]
    assert res["char_count"] <= 2200

def test_tiktok_export(mock_session_clip):
    """Verify TikTok export package formatting."""
    res = api_export_clip_package(mock_session_clip, "tiktok")
    assert res["platform"] == "tiktok"
    assert "#fyp" in res["hashtags"]
    assert len(res["hashtags"]) <= 6
    assert len(res["formatted_text"]) <= 2200
    assert res["char_count"] <= 2200

def test_unsupported_platform(mock_session_clip):
    """Verify unsupported platform returns HTTP 400."""
    with pytest.raises(HTTPException) as excinfo:
        api_export_clip_package(mock_session_clip, "myspace")
    assert excinfo.value.status_code == 400
    assert "Unsupported platform" in str(excinfo.value.detail)

def test_nonexistent_clip():
    """Verify missing clip returns HTTP 404."""
    with pytest.raises(HTTPException) as excinfo:
        api_export_clip_package("session_nonexistent:clip_999", "tiktok")
    assert excinfo.value.status_code == 404
