"""Stage 5 Check: API endpoints and UI static asset verification."""

from pathlib import Path
from clipper.api import (
    api_get_settings,
    api_update_settings,
    api_create_clips,
    api_update_clip,
    api_regenerate_text,
    api_render_clip,
    ClipRequest,
    ClipUpdateRequest,
    SettingsUpdateRequest,
    STATIC_DIR,
)

def test_static_ui_served():
    index_file = STATIC_DIR / "index.html"
    assert index_file.exists()
    text = index_file.read_text(encoding="utf-8")
    assert "Clipper" in text
    assert "Video or stream link" in text
    assert "Ranked clips" in text

def test_static_css_contains_spec_theme():
    css_file = STATIC_DIR / "style.css"
    assert css_file.exists()
    text = css_file.read_text(encoding="utf-8")
    assert "#C93A18" in text.upper() or "#c93a18" in text.lower()
    assert "#F6F5F1" in text.upper() or "#f6f5f1" in text.lower()
    assert "Inter" in text

def test_settings_api_get_and_put():
    data = api_get_settings()
    assert "record_height" in data
    assert "spike_min_msgs" in data

    updated = api_update_settings(SettingsUpdateRequest(record_height=1080, spike_min_msgs=150))
    assert updated["record_height"] == 1080
    assert updated["spike_min_msgs"] == 150

def test_clip_patch_and_regenerate(test_video_path):
    session_data = api_create_clips(ClipRequest(url=str(test_video_path), top_n=2))
    sess_id = session_data["id"]
    clip_id = session_data["clips"][0]["id"]
    composite_id = f"{sess_id}:{clip_id}"
    try:
        # PATCH clip
        patched = api_update_clip(composite_id, ClipUpdateRequest(
            title="Updated Custom Title",
            aspect="4:5",
            framing="crop_to_face",
        ))
        assert patched["title"] == "Updated Custom Title"
        assert patched["aspect"] == "4:5"
        assert patched["framing"] == "crop_to_face"

        # Regenerate metadata
        regen = api_regenerate_text(composite_id)
        assert "title" in regen

        # Render clip
        render_data = api_render_clip(composite_id)
        assert render_data["success"] is True
        assert "rendered_url" in render_data
    finally:
        import shutil
        from clipper.config import DATA_OUT_DIR
        shutil.rmtree(DATA_OUT_DIR / sess_id, ignore_errors=True)
