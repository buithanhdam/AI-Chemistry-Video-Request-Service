import json
import re

from src.logger import get_formatted_logger

logger = get_formatted_logger("json_parser")

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_candidates(raw: str) -> list[str]:
    """Trả về các ứng viên text JSON theo thứ tự ưu tiên."""
    raw = raw.strip()
    candidates = [raw]

    # 1) Trích nội dung trong ```json ... ``` hoặc ``` ... ```
    for match in _FENCE_RE.finditer(raw):
        candidates.append(match.group(1).strip())

    # 2) Bóc đoạn { ... } / [ ... ] ngoài cùng nhất
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = raw.find(open_ch)
        end = raw.rfind(close_ch)
        if start != -1 and end > start:
            candidates.append(raw[start : end + 1])

    return candidates


def _repair(text: str) -> str:
    """Sửa vài lỗi phổ biến: dấu phẩy cuối, booleans/thay None, chú thích line."""
    # bỏ comment // và #
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"#[^\n]*", "", text)
    # bỏ dấu phẩy trailing trước } hoặc ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text.strip()


def parse_json(raw: str | None) -> dict | list | None:
    """
    Parse JSON 'chiện':
    - thuần JSON
    - bọc trong ```json ... ```
    - JSON kèm text thừa trước/sau
    - dấu phẩy trailing, chuỗi 'None'/'null' lộn xộn
    Trả None nếu thất bại mọi cách (log warning, không raise).
    """
    if not raw or not isinstance(raw, str):
        logger.warning("parse_json: input rỗng hoặc không phải str")
        return None

    for candidate in _extract_candidates(raw):
        for attempt in (candidate, _repair(candidate)):
            try:
                data = json.loads(attempt)
                logger.debug(f"parse_json: OK (len={len(str(attempt))})")
                return data
            except (json.JSONDecodeError, ValueError):
                continue

    logger.warning("parse_json: không parse được JSON từ input")
    return None