"""Unit tests for background job disk persistence and restart recovery."""

import json
from pathlib import Path
from clipper.jobs import JobManager

def test_jobs_disk_persistence_and_restart_reconciliation(tmp_path):
    jobs_file = tmp_path / "jobs.json"

    # 1. Start JobManager instance A and create an in-flight job
    jm1 = JobManager(persistence_file=jobs_file)
    job = jm1.create_job("clip_generation", {"url": "https://example.com/stream"})
    job.update(stage="transcribing", progress=45, message="Transcribing speech chunks...")

    assert jobs_file.exists()
    disk_data = json.loads(jobs_file.read_text(encoding="utf-8"))
    assert job.id in disk_data
    assert disk_data[job.id]["status"] == "running"
    assert disk_data[job.id]["progress"] == 45
    assert disk_data[job.id]["stage"] == "transcribing"

    # 2. Simulate server restart: initialize JobManager instance B on the same jobs_file
    jm2 = JobManager(persistence_file=jobs_file)
    recovered_job = jm2.get_job(job.id)

    assert recovered_job is not None
    assert recovered_job.status == "failed"
    assert recovered_job.error == "interrupted by restart"
    assert "interrupted by restart" in recovered_job.message

    # 3. Create completed job on jm2 and verify it stays completed across another restart
    completed_job = jm2.create_job("clip_render", {"clip_id": "clip_1"})
    completed_job.complete({"file_path": "clip_1.mp4"})

    jm3 = JobManager(persistence_file=jobs_file)
    reloaded_completed = jm3.get_job(completed_job.id)
    assert reloaded_completed.status == "completed"
    assert reloaded_completed.error is None
    assert reloaded_completed.progress == 100
