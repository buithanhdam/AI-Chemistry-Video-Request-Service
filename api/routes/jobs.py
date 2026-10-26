from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.deps import get_job_store
from api.schemas import (
    CreateJobRequest,
    JobCreatedResponse,
    JobResponse,
    JobResult,
    JobStatus,
)
from src.logger import get_formatted_logger
from src.models.job import Job
from src.store.memory import InMemoryJobStore

logger = get_formatted_logger("api.jobs")

router = APIRouter()


def _iso(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        status=JobStatus(str(job.status)),
        query=job.query,
        progress=job.progress,
        result=JobResult(**job.result) if job.result else None,
        error=job.error,
        created_at=_iso(job.created_at),
        updated_at=_iso(job.updated_at),
    )


@router.post("/jobs", response_model=JobCreatedResponse, status_code=202)
async def create_job(
    req: CreateJobRequest,
    background_tasks: BackgroundTasks,
    store: InMemoryJobStore = Depends(get_job_store),
) -> JobCreatedResponse:
    job_id = f"job_{uuid4().hex[:8]}"
    job = Job(job_id=job_id, query=req.query)
    store.create(job)
    logger.info(f"Job created: {job_id} query={req.query[:80]!r}")

    # Pipeline runner import muộn để tránh circular + cho app khởi động
    # ngay cả khi pipeline chưa hoàn chỉnh.
    try:
        from src.pipeline.runner import run_pipeline

        background_tasks.add_task(run_pipeline, job_id)
        logger.info(f"Background pipeline scheduled: {job_id}")
    except ImportError as exc:
        logger.error(f"Pipeline runner not available: {exc}")
        store.update(job_id, status="FAILED", error="pipeline runner not available")

    return JobCreatedResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=_iso(job.created_at),
    )


@router.get("/jobs", response_model=JobResponse)
async def get_job_by_query(
    job_id: str,
    store: InMemoryJobStore = Depends(get_job_store),
) -> JobResponse:
    """Hỗ trợ GET /jobs?job_id=... (Postman-style query param)."""
    return await get_job(job_id, store)


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    store: InMemoryJobStore = Depends(get_job_store),
) -> JobResponse:
    job = store.get(job_id)
    if not job:
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    logger.debug(f"Job polled: {job_id} status={job.status}")
    return _to_response(job)