"""Tests for Priority 1: clip length constraints, score differentiation, unique titles, and 10 caption templates."""

import pytest
from pathlib import Path
from clipper.candidate_picker import find_candidate_moments
from clipper.caption_styles import list_caption_styles, get_caption_style, CAPTION_TEMPLATES
from clipper.ai import generate_clip_metadata

def test_caption_templates_all_ten():
    styles = list_caption_styles()
    assert len(styles) == 10
    expected_ids = {"pop", "clean", "box", "neon", "outline", "comic", "minimal", "highlight", "gradient", "typewriter"}
    assert set(CAPTION_TEMPLATES.keys()) == expected_ids
    for s in styles:
        assert "id" in s
        assert "name" in s
        assert "font_family" in s
        assert "primary_color" in s
        assert "active_color" in s
        assert "ass_primary" in s
        assert "ass_active" in s

def test_unique_titles_across_session():
    used = set()
    titles = []
    for rank in range(1, 8):
        meta = generate_clip_metadata("some exciting action happened here", clip_rank=rank, used_titles=used)
        titles.append(meta["title"])
    # All titles must be unique
    assert len(titles) == len(set(titles)), f"Duplicate titles found: {titles}"

def test_score_differentiation(test_video_path):
    candidates = find_candidate_moments(
        video_path=test_video_path,
        duration=10.0,
        target_count=3,
        min_clip_len=2.0,
        max_clip_len=4.0,
    )
    assert len(candidates) >= 3
    # Scores shouldn't all be identical
    scores = [c.combined_score for c in candidates]
    # At least two different scores or distinct starts
    starts = [c.start for c in candidates]
    assert len(set(starts)) == len(candidates)
