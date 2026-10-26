"""Knowledge base loader: 3 query cố định → YAML file."""
from pathlib import Path
from typing import Optional

import yaml

from src.logger import get_formatted_logger

logger = get_formatted_logger("knowledge")

_KNOWLEDGE_DIR = Path(__file__).resolve().parent

_CACHE: dict[str, dict] = {}


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_all() -> dict[str, dict]:
    """Load mọi YAML trong src/knowledge/ (cache theo path)."""
    result = {}
    for path in sorted(_KNOWLEDGE_DIR.glob("*.yaml")):
        if path.name not in _CACHE:
            try:
                _CACHE[path.name] = _load_yaml(path)
                logger.debug(f"Loaded knowledge: {path.name}")
            except yaml.YAMLError as exc:
                logger.error(f"YAML parse fail {path.name}: {exc}")
                _CACHE[path.name] = {}
        result[path.stem] = _CACHE[path.name]
    if not result:
        logger.warning("Knowledge base trống: không tìm thấy file YAML nào")
    return result


def get_knowledge(query: str) -> Optional[dict]:
    """Tìm knowledge khớp query (exact → chứa → filename)."""
    kb = load_all()
    normalized = query.strip().lower()

    for data in kb.values():
        if str(data.get("query", "")).strip().lower() == normalized:
            return data

    for data in kb.values():
        title = str(data.get("title", "")).lower()
        if title and title in normalized:
            return data

    for data in kb.values():
        for concept in data.get("key_concepts", []):
            words = [w for w in str(concept).lower().split() if len(w) > 4]
            if words and all(w in normalized for w in words):
                return data

    logger.warning(f"Không tìm thấy knowledge cho query: {query[:80]!r}")
    return None


def get_mock_script(query: str) -> Optional[dict]:
    """Lấy mock_script (fallback khi LLM fail) theo query."""
    data = get_knowledge(query)
    if not data:
        return None
    mock = data.get("mock_script")
    if not mock:
        logger.error(f"Knowledge thiếu mock_script cho query: {query[:80]!r}")
    return mock