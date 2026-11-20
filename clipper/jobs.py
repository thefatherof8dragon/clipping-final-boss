"""Background job manager with disk persistence for pipeline tasks."""

import os
import json
import time
import uuid
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List

from .config import DATA_DIR

logger = logging.getLogger("clipper.jobs")
JOBS_FILE = DATA_DIR / "jobs.json"


class Job:
    def __init__(
        self,
        job_id: str,
        job_type: str,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "pending",
        stage: str = "queued",
        progress: int = 0,
        message: str = "Job queued...",
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        created_at: Optional[float] = None,
        updated_at: Optional[float] = None,
        completed_at: Optional[float] = None,
        on_change: Optional[Any] = None,
    ):
        self.id = job_id
        self.type = job_type
        self.metadata = metadata or {}
        self.status = status  # pending, running, completed, failed
        self.stage = stage
        self.progress = progress
        self.message = message
        self.error = error
        self.result = result
        self.created_at = created_at or time.time()
        self.updated_at = updated_at or time.time()
        self.completed_at = completed_at
        self._on_change = on_change

    def update(self, stage: str, progress: int, message: str) -> None:
        self.status = "running"
        self.stage = stage
        self.progress = max(0, min(100, int(progress)))
        self.message = message
        self.updated_at = time.time()
        logger.info(f"[Job {self.id}] [{self.stage}] {self.progress}% - {self.message}")
        if self._on_change:
            self._on_change()

    def complete(self, result: Dict[str, Any]) -> None:
        self.status = "completed"
        self.progress = 100
        self.stage = "complete"
        self.message = "Complete!"
        self.result = result
        self.updated_at = time.time()
        self.completed_at = time.time()
        logger.info(f"[Job {self.id}] Completed successfully")
        if self._on_change:
            self._on_change()

    def fail(self, error_message: str) -> None:
        self.status = "failed"
        self.error = error_message
        self.message = f"Failed: {error_message}"
        self.updated_at = time.time()
        self.completed_at = time.time()
        logger.error(f"[Job {self.id}] Failed: {error_message}")
        if self._on_change:
            self._on_change()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], on_change: Optional[Any] = None) -> "Job":
        return cls(
            job_id=data["id"],
            job_type=data.get("type", "clip_generation"),
            metadata=data.get("metadata", {}),
            status=data.get("status", "pending"),
            stage=data.get("stage", "queued"),
            progress=int(data.get("progress", 0)),
            message=data.get("message", "Job queued..."),
            error=data.get("error"),
            result=data.get("result"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            completed_at=data.get("completed_at"),
            on_change=on_change,
        )


class JobManager:
    """Thread-safe job registry backed by disk persistence."""

    def __init__(self, persistence_file: Path = JOBS_FILE):
        self.persistence_file = persistence_file
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self.load_persisted_jobs()

    def _persist(self) -> None:
        """Saves current jobs state to disk atomically."""
        try:
            self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.persistence_file.with_suffix(".tmp")
            data = {j_id: j.to_dict() for j_id, j in self._jobs.items()}
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(self.persistence_file)
        except Exception as e:
            logger.error(f"Failed to persist jobs to {self.persistence_file}: {e}")

    def load_persisted_jobs(self) -> None:
        """Loads jobs from disk and reconciles interrupted unfinished jobs."""
        with self._lock:
            if not self.persistence_file.exists():
                return
            try:
                with open(self.persistence_file, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed reading jobs file {self.persistence_file}: {e}")
                return

            loaded_count = 0
            interrupted_count = 0
            for j_id, j_dict in raw_data.items():
                job = Job.from_dict(j_dict, on_change=self._persist)
                # Reconcile mid-flight jobs interrupted by shutdown or restart
                if job.status in ("running", "pending") and job.stage != "complete":
                    job.fail("interrupted by restart")
                    interrupted_count += 1
                self._jobs[j_id] = job
                loaded_count += 1

            if interrupted_count > 0:
                logger.warning(
                    f"[Jobs Recovery] Reconciled {interrupted_count} in-flight job(s) as 'interrupted by restart'"
                )
            logger.info(f"[Jobs Recovery] Loaded {loaded_count} job(s) from {self.persistence_file}")
            self._persist()

    def create_job(self, job_type: str, metadata: Optional[Dict[str, Any]] = None) -> Job:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = Job(job_id, job_type, metadata, on_change=self._persist)
        with self._lock:
            self._jobs[job_id] = job
            self._persist()
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [j.to_dict() for j in self._jobs.values()]


job_manager = JobManager()
