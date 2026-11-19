"""Stage 3 Check: Render one clip in all four ratios and both framing modes without errors."""

import pytest
from pathlib import Path
from clipper.renderer import render_clip, ASPECT_RATIOS

@pytest.mark.parametrize("aspect", ["9:16", "1:1", "4:5", "16:9"])
def test_render_all_aspect_ratios_blur_fit(test_video_path, sample_words, tmp_path, aspect):
    """Verifies rendering across all four aspect ratios in blur_fit mode."""
    out_video = tmp_path / f"rendered_{aspect.replace(':', '_')}.mp4"
    ok = render_clip(
        input_video=test_video_path,
        output_video=out_video,
        aspect_ratio=aspect,
        framing="blur_fit",
        words=sample_words,
        caption_style="karaoke",
        captions_on=True,
        hook_text="OMG WAIT FOR IT!",
        trim_start=1.0,
        trim_end=4.0,
    )
    assert ok is True, f"Failed rendering aspect ratio {aspect}"
    assert out_video.exists()
    assert out_video.stat().st_size > 1000

@pytest.mark.parametrize("framing", ["blur_fit", "crop_to_face"])
def test_render_both_framing_modes(test_video_path, sample_words, tmp_path, framing):
    """Verifies rendering across both framing modes (blur_fit and crop_to_face)."""
    out_video = tmp_path / f"rendered_{framing}.mp4"
    ok = render_clip(
        input_video=test_video_path,
        output_video=out_video,
        aspect_ratio="9:16",
        framing=framing,
        words=sample_words,
        caption_style="tiktok",
        captions_on=True,
        hook_text="TESTING FRAMING",
        trim_start=0.5,
        trim_end=3.5,
    )
    assert ok is True, f"Failed rendering framing mode {framing}"
    assert out_video.exists()
    assert out_video.stat().st_size > 1000

def test_render_clean_minimal_subtitles_off(test_video_path, tmp_path):
    """Verifies rendering with captions turned off."""
    out_video = tmp_path / "rendered_no_subs.mp4"
    ok = render_clip(
        input_video=test_video_path,
        output_video=out_video,
        aspect_ratio="1:1",
        framing="blur_fit",
        captions_on=False,
    )
    assert ok is True
    assert out_video.exists()
