"""Stage 4 Check: AI text generation (no-key mode & providers) and thumbnail generation."""

from pathlib import Path
from clipper.ai import generate_clip_metadata, extract_fallback_metadata
from clipper.thumbnail import create_thumbnail, find_best_frame

def test_no_key_metadata_generation():
    transcript = "You will not believe what just happened! This is the most insane play in gaming history. Watch until the end."
    meta = extract_fallback_metadata(transcript, clip_rank=1)
    assert "title" in meta
    assert len(meta["title"]) > 0
    assert "caption" in meta
    assert len(meta["caption"]) > 0
    assert "hashtags" in meta
    assert len(meta["hashtags"]) >= 3
    assert all(h.startswith("#") for h in meta["hashtags"])
    assert meta["provider"] == "local_fallback"

def test_generate_clip_metadata_dispatcher():
    meta = generate_clip_metadata("Testing speech transcript with no API keys set.", clip_rank=2)
    assert "title" in meta
    assert "caption" in meta
    assert "hashtags" in meta

def test_best_frame_extraction(test_video_path):
    frame = find_best_frame(test_video_path, sample_count=5)
    assert frame is not None
    assert len(frame.shape) == 3
    assert frame.shape[0] > 0 and frame.shape[1] > 0

def test_thumbnail_creation(test_video_path, tmp_path):
    out_thumb = tmp_path / "test_thumb.jpg"
    ok = create_thumbnail(
        video_path=test_video_path,
        title="INSANE WINNER MOMENT!",
        output_path=out_thumb,
        aspect_ratio="9:16",
    )
    assert ok is True
    assert out_thumb.exists()
    assert out_thumb.stat().st_size > 1000
