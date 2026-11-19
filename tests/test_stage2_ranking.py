"""Stage 2 Check: Unit tests for ranking math and API returns ranked clips."""

import pytest
from clipper.ranker import calculate_score, rank_and_rename_clips
from clipper.api import api_create_clips, api_get_session_clips, ClipRequest

def test_ranking_math_with_chat():
    # 100 on everything -> 100
    assert calculate_score(100, 100, 100, 100, 100, has_chat=True) == 100.0
    # 0 on everything -> 0
    assert calculate_score(0, 0, 0, 0, 0, has_chat=True) == 0.0

    # Specific calculation:
    # 0.30*80 + 0.25*60 + 0.20*70 + 0.15*50 + 0.10*40 = 24 + 15 + 14 + 7.5 + 4 = 64.5
    assert calculate_score(80, 60, 70, 50, 40, has_chat=True) == 64.5

def test_ranking_math_without_chat_redistributed():
    # Weights redistributed over 0.75:
    # 100 on everything -> 100
    assert calculate_score(100, 0, 100, 100, 100, has_chat=False) == 100.0

    # hook: 0.3/0.75=0.4, emotion: 0.2/0.75=0.2667, story: 0.15/0.75=0.2, trend: 0.1/0.75=0.1333
    # 0.40*80 (32) + (0.2/0.75)*70 (18.667) + 0.20*50 (10) + (0.1/0.75)*40 (5.333) = 66.0
    expected = 0.40 * 80 + (0.20 / 0.75) * 70 + 0.20 * 50 + (0.10 / 0.75) * 40
    assert calculate_score(80, 0, 70, 50, 40, has_chat=False) == round(expected, 1)

def test_rank_ordering_and_renaming(tmp_path):
    clip_a = tmp_path / "temp_a.mp4"
    clip_b = tmp_path / "temp_b.mp4"
    clip_a.write_bytes(b"dummy_a")
    clip_b.write_bytes(b"dummy_b")

    clips = [
        {"id": "a", "file_path": str(clip_a), "title": "Second Best", "hook_score": 50, "emotion_score": 50, "story_score": 50, "trend_score": 50, "chat_score": 0},
        {"id": "b", "file_path": str(clip_b), "title": "Top Tier", "hook_score": 90, "emotion_score": 90, "story_score": 90, "trend_score": 90, "chat_score": 0},
    ]

    ranked = rank_and_rename_clips(clips, tmp_path, has_chat=False)
    assert ranked[0]["rank"] == 1
    assert ranked[0]["title"] == "Top Tier"
    assert ranked[0]["filename"].startswith("01_")

    assert ranked[1]["rank"] == 2
    assert ranked[1]["title"] == "Second Best"
    assert ranked[1]["filename"].startswith("02_")

def test_api_get_session_clips(test_video_path):
    # Process session first via API
    resp_data = api_create_clips(ClipRequest(url=str(test_video_path), top_n=3))
    assert "id" in resp_data
    session_id = resp_data["id"]

    # Call GET /api/sessions/{id}/clips via API
    data = api_get_session_clips(session_id)
    assert "clips" in data
    assert len(data["clips"]) >= 3
    first = data["clips"][0]
    assert first["rank"] == 1
    assert "scores" in first
    assert "reason" in first
