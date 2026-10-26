"""LLM client: Gemini wrapper + mock fallback. Boundary thay provider."""
import asyncio
from typing import Any, Optional, Protocol

import yaml

from src.config import settings
from src.logger import get_formatted_logger
from src.utils import parse_json

logger = get_formatted_logger("llm")


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> Optional[dict]:
        """Trả dict đã parse, hoặc None nếu fail."""
        ...


class GeminiClient:
    def __init__(self, api_key: str, timeout: int) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY trống")
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._timeout = timeout
        self._model = "gemini-3.1-flash-lite"

    async def generate(self, prompt: str) -> Optional[dict]:
        def _call() -> str:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            return response.text or ""

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(_call), timeout=self._timeout
            )
        except (asyncio.TimeoutError, TimeoutError):
            logger.warning(f"Gemini timeout sau {self._timeout}s")
            return None
        except Exception as exc:
            logger.warning(f"Gemini call fail: {exc}")
            return None

        data = parse_json(raw)
        if data is None:
            logger.warning("Gemini trả text không parse được JSON")
        return data


class MockLLMClient:
    """Trả mock_script từ knowledge YAML luôn (provider fallback)."""

    async def generate(self, prompt: str) -> Optional[dict]:
        # Prompt có dạng "Query: ..." → trích query ra để dò knowledge.
        import re

        match = re.search(r"^Query:\s*(.+)$/m", prompt, re.MULTILINE)
        if not match:
            return None
        from src.knowledge.loader import get_mock_script

        mock = get_mock_script(match.group(1).strip())
        if mock is None:
            logger.warning("Mock LLM: không có mock cho query")
        return mock


def get_llm_client() -> Optional[LLMClient]:
    """Gemini nếu có key, ngược lại None (caller sẽ dùng mock)."""
    try:
        client = GeminiClient(settings.GEMINI_API_KEY, settings.TIMEOUT_SECONDS)
        logger.info("LLM provider: Gemini")
        return client
    except ValueError:
        logger.info("LLM provider: mock (không có GEMINI_API_KEY)")
        return None


def knowledge_to_yaml(data: dict) -> str:
    """Chỉ giữ key giáo dục, bỏ mock_script khỏi context."""
    context = {
        k: v for k, v in data.items() if k not in ("mock_script",)
    }
    return yaml.safe_dump(context, allow_unicode=True, sort_keys=False)


def dumps_yaml(data: Any) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)