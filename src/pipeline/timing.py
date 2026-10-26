"""Helper đo thời gian từng step pipeline để log debug."""
import time
from contextlib import contextmanager
from typing import Callable, Iterator

from src.logger import get_formatted_logger

logger = get_formatted_logger("pipeline.timing")


@contextmanager
def step_timer(job_id: str, step: str, log: Callable[[str], None] = None) -> Iterator[dict]:
    """Context manager: log start/duration của 1 step pipeline.

    Usage:
        with step_timer(job_id, "generating_script") as t:
            ...
            t["detail"] = "provider=gemini attempt=2"
    """
    info = log or (lambda msg: logger.info(msg))
    start = time.perf_counter()
    info(f"[{job_id}] STEP START  : {step}")
    meta: dict = {}
    try:
        yield meta
    except Exception as exc:
        elapsed = time.perf_counter() - start
        info(f"[{job_id}] STEP FAIL  : {step} ({elapsed:.2f}s) error={exc}")
        raise
    elapsed = time.perf_counter() - start
    detail = f" | {meta['detail']}" if meta.get("detail") else ""
    info(f"[{job_id}] STEP DONE  : {step} ({elapsed:.2f}s){detail}")