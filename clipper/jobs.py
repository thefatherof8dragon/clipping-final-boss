"""Background job manager for long-running pipeline tasks."""

import time
import uuid
import logging
import threading
from typing import Dict, Any, Optional, Callable

logger = logging.getLogger("clipper.jobs")

class Job:
    def __init__(self, job_id: str, job_type: str, metadata: Optional[Dict[str, Any]] = None):
        self.id = job_id
        self.type = job_type
        self.metadata = metadata or {}
        self.status = "pending"  # pending, running, completed, failed
        self.stage = "queued"
        self.progress = 0
        self.message = "Job queued..."
        self.error: Optional[str] = None
        self.result: Optional[Dict[str, Any]] = None
        self.created_at = time.time()
        self.updated_at = time.time()
        self.completed_at: Optional[float] = None

    def update(self, stage: str, progress: int, message: str) -> None:
        self.status = "running"
        self.stage = stage
        self.progress = max(0, min(100, int(progress)))
        self.message = message
        self.updated_at = time.time()
        logger.info(f"[Job {self.id}] [{self.stage}] {self.progress}% - {self.message}")

    def complete(self, result: Dict[str, Any]) -> None:
        self.status = "completed"
        self.progress = 100
        self.stage = "complete"
        self.message = "Complete!"
        self.result = result
        self.updated_at = time.time()
        self.completed_at = time.time()
        logger.info(f"[Job {self.id}] Completed successfully")

    def fail(self, error_message: str) -> None:
        self.status = "failed"
        self.error = error_message
        self.message = f"Failed: {error_message}"
        self.updated_at = time.time()
        self.completed_at = time.time()
        logger.error(f"[Job {self.id}] Failed: {error_message}")

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
        }

class JobManager:
    """Thread-safe in-memory job registry."""

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, job_type: str, metadata: Optional[Dict[str, Any]] = None) -> Job:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = Job(job_id, job_type, metadata)
        with self._lock:
            self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[Dict[str, Any]]:
        with self._lock:
            return [j.to_dict() for j in self._jobs.values()]

job_manager = JobManager()
