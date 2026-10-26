from datetime import datetime
from threading import Lock
from typing import Optional

from src.logger import get_formatted_logger
from src.models.job import Job

logger = get_formatted_logger("job_store")


class InMemoryJobStore:
    """Thread-safe in-memory job store (dict + lock)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.job_id] = job
            logger.debug(f"Job created: {job.job_id}")
            return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning(f"update: job not found: {job_id}")
                return None
            for key, value in kwargs.items():
                if not hasattr(job, key):
                    logger.warning(f"update: unknown field '{key}' on Job")
                    continue
                setattr(job, key, value)
            job.updated_at = datetime.utcnow()
            logger.debug(f"Job updated: {job_id} {kwargs}")
            return job

    def all(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())


job_store = InMemoryJobStore()