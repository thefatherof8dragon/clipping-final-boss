"""Unit tests for progress callback consistency across all pipeline stages."""

import pytest
from clipper.jobs import job_manager, Job

def test_on_progress_signature_and_stages():
    """Verify on_progress accepts def on_progress(pct: float, msg: str = '', **kw)."""
    job = job_manager.create_job("clip_generation", {"url": "test"})

    def on_progress(pct: float, msg: str = "", **kw) -> None:
        stage = kw.get("stage")
        if isinstance(pct, str):
            if isinstance(msg, (int, float)):
                pct, msg = float(msg), pct
            else:
                stage = pct
                pct = 0.0
        pct_float = float(pct) if isinstance(pct, (int, float)) else 0.0
        pct_int = max(0, min(100, int(round(pct_float))))

        if not stage:
            if pct_int < 20: stage = "download"
            elif pct_int < 45: stage = "transcribe"
            elif pct_int < 65: stage = "moments"
            elif pct_int < 85: stage = "rank"
            elif pct_int < 100: stage = "render"
            else: stage = "complete"

        job.update(stage, pct_int, str(msg))

    # Stage 1: download
    on_progress(10.0, "Downloading or loading video...", stage="download")
    assert job.stage == "download"
    assert job.progress == 10
    assert "Downloading" in job.message

    # Stage 2: transcribe
    on_progress(25.0, "Transcribing audio locally with faster-whisper...", stage="transcribe")
    assert job.stage == "transcribe"
    assert job.progress == 25
    assert "Transcribing" in job.message

    # Stage 3: hooks / moments
    on_progress(50.0, "Detecting hooks, loudness, and chat spikes...", stage="moments")
    assert job.stage == "moments"
    assert job.progress == 50
    assert "Detecting hooks" in job.message

    # Stage 4: rank & cut
    on_progress(70.0, "Cutting candidate clips with FFmpeg...", stage="rank")
    assert job.stage == "rank"
    assert job.progress == 70

    on_progress(84.0, "Scoring and ranking clips...", stage="rank")
    assert job.stage == "rank"
    assert job.progress == 84

    # Stage 5: render
    on_progress(90.0, "Generating poster frames and vertical video thumbnails...", stage="render")
    assert job.stage == "render"
    assert job.progress == 90

    # Stage 6: complete
    on_progress(100.0, "Complete! Ranked short clips ready.", stage="complete")
    assert job.stage == "complete"
    assert job.progress == 100

def test_on_progress_default_and_legacy_arguments():
    """Verify on_progress works with default msg, positional args, and keyword args."""
    job = job_manager.create_job("clip_generation", {"url": "test2"})

    def on_progress(pct: float, msg: str = "", **kw) -> None:
        stage = kw.get("stage")
        if isinstance(pct, str):
            if isinstance(msg, (int, float)):
                pct, msg = float(msg), pct
            else:
                stage = pct
                pct = 0.0
        pct_float = float(pct) if isinstance(pct, (int, float)) else 0.0
        pct_int = max(0, min(100, int(round(pct_float))))

        if not stage:
            if pct_int < 20: stage = "download"
            elif pct_int < 45: stage = "transcribe"
            elif pct_int < 65: stage = "moments"
            elif pct_int < 85: stage = "rank"
            elif pct_int < 100: stage = "render"
            else: stage = "complete"

        job.update(stage, pct_int, str(msg))

    # Single argument call (msg defaults to "")
    on_progress(15.5)
    assert job.progress == 16
    assert job.stage == "download"

    # Two positional arguments
    on_progress(40.0, "Processing transcription")
    assert job.progress == 40
    assert job.stage == "transcribe"
    assert job.message == "Processing transcription"

    # Stage passed via kwargs
    on_progress(75.0, "Cutting clip #3", stage="cut")
    assert job.progress == 75
    assert job.stage == "cut"

def test_failed_job_preserves_stage_and_never_shows_ready():
    """A failed job must keep its stage and error, and never show ready/100%."""
    job = job_manager.create_job("clip_generation", {"url": "test3"})
    job.update("transcribe", 30, "Transcribing...")
    assert job.stage == "transcribe"
    assert job.progress == 30

    job.fail("CUDA out of memory")
    assert job.status == "failed"
    assert job.stage == "transcribe"
    assert job.progress == 30
    assert job.progress != 100
    assert "CUDA out of memory" in job.error
