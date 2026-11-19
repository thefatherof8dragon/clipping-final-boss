"""Stage 1 Check: Core pipeline cuts at least 3 mp4 clips into data/out/session_N/."""

from pathlib import Path
from clipper.downloader import download_or_load
from clipper.transcriber import transcribe
from clipper.candidate_picker import find_candidate_moments
from clipper.cutter import cut_clip
from clipper.session import process_video_pipeline, DATA_OUT_DIR

def test_local_file_download_and_probe(test_video_path):
    res = download_or_load(str(test_video_path), "test_stage1_probe")
    assert res["file_path"].exists()
    assert res["duration"] >= 9.0
    assert res["is_local"] is True

def test_transcription_runs(test_video_path):
    # Even on synthetic video with sine tone, transcription runs without crashing
    res = transcribe(test_video_path)
    assert "segments" in res
    assert "full_text" in res

def test_candidate_picker(test_video_path):
    candidates = find_candidate_moments(
        video_path=test_video_path,
        duration=10.0,
        target_count=3,
        min_clip_len=2.0,
        max_clip_len=5.0,
    )
    assert len(candidates) >= 3
    for c in candidates:
        assert c.end > c.start
        assert c.combined_score > 0

def test_cutter_creates_mp4(test_video_path, tmp_path):
    out_clip = tmp_path / "test_cut.mp4"
    ok = cut_clip(test_video_path, out_clip, start=1.0, end=4.0)
    assert ok is True
    assert out_clip.exists()
    assert out_clip.stat().st_size > 1000

def test_stage1_pipeline_generates_at_least_3_clips(test_video_path):
    """Stage 1 check requirement: produces at least 3 mp4 clips in data/out/session_N/."""
    session = process_video_pipeline(source=str(test_video_path), top_n=3)
    assert "id" in session
    session_dir = DATA_OUT_DIR / session["id"]
    try:
        assert session_dir.exists()
        clips = list(session_dir.glob("*.mp4"))
        assert len(clips) >= 3, f"Expected at least 3 clips in {session_dir}, got {len(clips)}"
    finally:
        import shutil
        shutil.rmtree(session_dir, ignore_errors=True)
