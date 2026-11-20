"""Unit tests for Gaming and GTA VI Launch presets in game detection and candidate scoring."""

import pytest
import numpy as np
from pathlib import Path
from clipper.games import detect, tags_of, name_of, get_game_rules, GAMES
from clipper.candidate_picker import (
    calculate_candidate_scores,
    find_candidate_moments,
    GAMING_KEYWORDS,
    GTA6_KEYWORDS,
)
from clipper.ai import extract_local_metadata, generate_clip_metadata

def test_game_detection_and_tagging():
    """Verify 23 known games are detected from title and hashtags are generated."""
    # GTA 6 aliases
    gta6, tags = detect("EXCLUSIVE: GTA 6 Gameplay Walkthrough")
    assert gta6 == "Grand Theft Auto VI"
    assert "GTA6" in tags
    assert "ViceCity" in tags

    gta6_spelled, _ = detect("grand theft auto vi leaks reaction")
    assert gta6_spelled == "Grand Theft Auto VI"

    # GTA 5
    gta5, tags5 = detect("GTA V RP NoPixel stream")
    assert gta5 == "Grand Theft Auto V"
    assert "GTA5" in tags5

    # Fortnite
    fn, fntags = detect("Fortnite ranked solo victory royale")
    assert fn == "Fortnite"
    assert "Fortnite" in fntags

    # Non-game titles
    no_game, notags = detect("Just chatting with subscribers today")
    assert no_game is None
    assert notags == []

    # False positive prevention
    rust_cleaning, _ = detect("Rust removal and restoration")
    assert rust_cleaning is None

def test_game_prompt_rules():
    """Verify game rules prompt injection string."""
    rules = get_game_rules("Grand Theft Auto VI")
    assert "Grand Theft Auto VI" in rules
    assert "#GTA6" in rules
    assert "CLUTCH" in rules

    empty_rules = get_game_rules(None)
    assert empty_rules == ""

def test_gaming_preset_scoring():
    """Verify preset='gaming' boosts hook and trend scores for gaming action."""
    loudness = np.full(30, 50.0, dtype=np.float32)
    chat = np.zeros(30, dtype=np.float32)

    # Gaming phrase: "Insane clutch headshot to win the round!"
    text_gaming = "Insane clutch headshot to win the round! Look at that play."
    words_gaming = [{"word": w, "start": 0.0, "end": 1.0} for w in text_gaming.split()]

    score_without_preset = calculate_candidate_scores(
        start_sec=0.0,
        end_sec=10.0,
        loudness=loudness,
        transcript_segments=[],
        chat_density=chat,
        has_chat=False,
        window_words=words_gaming,
        window_text=text_gaming,
        preset=None,
    )

    score_with_gaming_preset = calculate_candidate_scores(
        start_sec=0.0,
        end_sec=10.0,
        loudness=loudness,
        transcript_segments=[],
        chat_density=chat,
        has_chat=False,
        window_words=words_gaming,
        window_text=text_gaming,
        preset="gaming",
    )

    assert score_with_gaming_preset["hook"] > score_without_preset["hook"]
    assert score_with_gaming_preset["trend"] > score_without_preset["trend"]
    assert score_with_gaming_preset["combined"] > score_without_preset["combined"]

def test_gta6_preset_scoring():
    """Verify preset='gta6' gives maximum priority to Vice City, heist, and GTA 6 triggers."""
    loudness = np.full(30, 50.0, dtype=np.float32)
    chat = np.zeros(30, dtype=np.float32)

    text_gta6 = "GTA 6 Vice City trailer reaction! Lucia and Jason are back."
    words_gta6 = [{"word": w, "start": 0.0, "end": 1.0} for w in text_gta6.split()]

    score_standard = calculate_candidate_scores(
        start_sec=0.0,
        end_sec=10.0,
        loudness=loudness,
        transcript_segments=[],
        chat_density=chat,
        has_chat=False,
        window_words=words_gta6,
        window_text=text_gta6,
        preset=None,
    )

    score_gta6 = calculate_candidate_scores(
        start_sec=0.0,
        end_sec=10.0,
        loudness=loudness,
        transcript_segments=[],
        chat_density=chat,
        has_chat=False,
        window_words=words_gta6,
        window_text=text_gta6,
        preset="gta6",
    )

    assert score_gta6["hook"] > score_standard["hook"]
    assert score_gta6["trend"] > score_standard["trend"]
    assert score_gta6["combined"] > score_standard["combined"]

def test_local_metadata_with_game_tags():
    """Verify metadata generator includes game tags when game is specified."""
    meta = extract_local_metadata(
        transcript_text="Look at this incredible mission in the city! We did it.",
        clip_rank=1,
        game="Grand Theft Auto VI",
    )
    assert "#GTA6" in meta["hashtags"]
    assert "#ViceCity" in meta["hashtags"]
    # Tags should be clean single words without spaces
    assert all(" " not in t and t.startswith("#") for t in meta["hashtags"])
