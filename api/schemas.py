from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ArtifactPaths(BaseModel):
    slides: list[str] = Field(default_factory=list)
    audio: list[str] = Field(default_factory=list)
    final_video: Optional[str] = None


class JobResult(BaseModel):
    script: Optional[dict[str, Any]] = None
    artifacts: ArtifactPaths = Field(default_factory=ArtifactPaths)


class CreateJobRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=300)


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    query: str
    progress: Optional[str] = None
    result: Optional[JobResult] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str


class ErrorResponse(BaseModel):
    detail: str