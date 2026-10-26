from src.store.memory import InMemoryJobStore, job_store  # noqa: F401


def get_job_store() -> InMemoryJobStore:
    """Dependency: trả về singleton in-memory job store."""
    return job_store