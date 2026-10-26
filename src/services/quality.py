"""Quality gate: kiểm tra script sau khi LLM trả về."""
from typing import Any, Optional

from src.logger import get_formatted_logger

logger = get_formatted_logger("quality")

REQUIRED_KEYS = ("title", "sections", "summary")
MIN_SECTIONS = 2
MAX_SECTIONS = 5
MIN_POINTS = 1
MAX_POINTS = 5
MIN_NARRATION_WORDS = 10


class QualityGateError(Exception):
    """Raise khi script không đạt quality gate."""


def validate_script(data: Optional[Any]) -> dict:
    """Raise QualityGateError nếu fail, ngược lại return data."""
    if not isinstance(data, dict):
        raise QualityGateError("Script không phải dict/JSON object")

    for key in REQUIRED_KEYS:
        if key not in data:
            raise QualityGateError(f"Thiếu key bắt buộc: {key}")

    if not str(data.get("title", "")).strip():
        raise QualityGateError("title rỗng")

    if not str(data.get("summary", "")).strip():
        raise QualityGateError("summary rỗng")

    sections = data.get("sections")
    if not isinstance(sections, list):
        raise QualityGateError("sections phải là list")
    if not (MIN_SECTIONS <= len(sections) <= MAX_SECTIONS):
        raise QualityGateError(
            f"Số sections phải trong [{MIN_SECTIONS}, {MAX_SECTIONS}], có {len(sections)}"
        )

    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise QualityGateError(f"Section {i} không phải object")
        if not str(section.get("heading", "")).strip():
            raise QualityGateError(f"Section {i}: heading rỗng")
        points = section.get("key_points")
        if not isinstance(points, list) or not (
            MIN_POINTS <= len(points) <= MAX_POINTS
        ):
            raise QualityGateError(
                f"Section {i}: key_points phải là list {MIN_POINTS}-{MAX_POINTS} phần tử"
            )
        if any(not str(p).strip() for p in points):
            raise QualityGateError(f"Section {i}: có key_point rỗng")
        narration = str(section.get("narration", ""))
        if len(narration.split()) < MIN_NARRATION_WORDS:
            raise QualityGateError(
                f"Section {i}: narration quá ngắn (<{MIN_NARRATION_WORDS} từ)"
            )

    logger.debug("Quality gate: PASS")
    return data


def check_quality(data: Optional[Any]) -> tuple[bool, Optional[str]]:
    """Non-raise version: return (ok, reason)."""
    try:
        validate_script(data)
        return True, None
    except QualityGateError as exc:
        return False, str(exc)