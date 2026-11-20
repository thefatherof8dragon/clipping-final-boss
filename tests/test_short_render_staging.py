"""Unit tests for short render staging and long path resilience in clipper/renderer.py."""

import os
from pathlib import Path
from clipper.renderer import render_clip, get_render_staging_dir

def test_short_staging_dir_exists_and_short():
    staging_dir = get_render_staging_dir()
    assert staging_dir.exists()
    assert len(str(staging_dir)) < 80

def test_render_with_deliberately_long_output_path(tmp_path):
    # Construct a deliberately deep and long destination path
    deep_subdirs = ["nested_subfolder_level_" + str(i).zfill(3) for i in range(1, 6)]
    long_dest_dir = tmp_path.joinpath(*deep_subdirs)
    long_dest_dir.mkdir(parents=True, exist_ok=True)
    long_output_mp4 = long_dest_dir / ("a_very_long_named_clip_export_with_extra_characters_to_simulate_deep_path_" * 2 + ".mp4")

    print(f"Testing with long path ({len(str(long_output_mp4))} chars): {long_output_mp4}")
    assert len(str(long_output_mp4)) > 150

    input_sample = Path("data/out/session_1/clip_1.mp4")
    if not input_sample.exists():
        input_sample = Path("data/in/session_2_source.mp4")

    words = [
        {"word": "Staging", "start": 0.0, "end": 0.6},
        {"word": "Test", "start": 0.7, "end": 1.2},
        {"word": "Passes", "start": 1.3, "end": 2.0},
    ]

    ok = render_clip(
        input_video=input_sample,
        output_video=long_output_mp4,
        aspect_ratio="9:16",
        framing="blur_fit",
        words=words,
        caption_style="karaoke",
        captions_on=True,
        hook_text="LONG PATH VERIFIED",
        trim_start=0.0,
        trim_end=2.0,
    )

    assert ok is True
    assert long_output_mp4.exists()
    assert long_output_mp4.stat().st_size > 5000
