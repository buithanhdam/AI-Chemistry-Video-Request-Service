from fastapi import FastAPI

from api.routes import jobs
from src.config import settings
from src.logger import get_formatted_logger

logger = get_formatted_logger("app")

app = FastAPI(
    title="Chemistry Learner Prototype",
    version="0.1.0",
    description="Async job API generating educational multimodal lessons (images + audio + video).",
)

app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok", "env": settings.PROJECT_ENV}


logger.info("FastAPI app initialized: Chemistry Learner Prototype v0.1.0")