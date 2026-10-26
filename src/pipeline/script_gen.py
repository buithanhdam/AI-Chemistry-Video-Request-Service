"""Script generation: LLM → validate → retry → mock fallback."""
import asyncio
import time

from src.config import settings
from src.knowledge.loader import get_mock_script
from src.llm.client import MockLLMClient, get_llm_client, knowledge_to_yaml
from src.llm.prompts import build_script_prompt
from src.logger import get_formatted_logger
from src.services.quality import QualityGateError, validate_script

logger = get_formatted_logger("script_gen")

_gemini = get_llm_client()
_mock = MockLLMClient()

_RAW_SNIPPET = 300


async def generate_script(query: str, knowledge: dict) -> dict:
    """LLM + retry + fallback. Luôn trả script hợp lệ hoặc raise."""
    prompt = build_script_prompt(query, knowledge_to_yaml(knowledge))
    attempts = max(1, settings.MAX_RETRIES)
    logger.info(f"Script gen start: retries={attempts} provider={'gemini' if _gemini else 'mock'}")

    for attempt in range(1, attempts + 1):
        t0 = time.perf_counter()
        try:
            raw = None
            if _gemini is not None:
                logger.debug(f"LLM call attempt {attempt}/{attempts}: prompt len={len(prompt)}")
                raw = await _gemini.generate(prompt)
                elapsed = time.perf_counter() - t0
                if raw is None:
                    logger.warning(
                        f"LLM attempt {attempt}/{attempts} FAILED ({elapsed:.2f}s): "
                        f"không parse được response"
                    )
                else:
                    logger.info(
                        f"LLM attempt {attempt}/{attempts} responded ({elapsed:.2f}s): "
                        f"raw={str(raw)[:_RAW_SNIPPET]!r}..."
                    )
            else:
                raw = await _mock.generate(prompt)
                logger.info(f"LLM (mock) attempt {attempt}: raw={str(raw)[:_RAW_SNIPPET]!r}")

            script = validate_script(raw)
            provider = "gemini" if _gemini is not None else "mock"
            logger.info(
                f"Script OK (provider={provider}, attempt={attempt}, "
                f"total={time.perf_counter() - t0:.2f}s): title={str(script.get('title'))[:60]!r}"
            )
            return script
        except QualityGateError as exc:
            logger.warning(
                f"Validate fail (attempt {attempt}/{attempts}, "
                f"{time.perf_counter() - t0:.2f}s): {exc}"
            )
        except Exception as exc:
            logger.warning(
                f"LLM call fail (attempt {attempt}/{attempts}, "
                f"{time.perf_counter() - t0:.2f}s): {exc}"
            )

        if attempt < attempts:
            logger.debug(f"Sleep 1s trước retry {attempt + 1}")
            await asyncio.sleep(1)

    logger.warning("Hết retry → fallback mock_script")
    mock = get_mock_script(query)
    if mock is None:
        raise QualityGateError(f"Không có mock_script fallback cho query: {query[:80]}")
    script = validate_script(mock)
    logger.info(f"Script fallback mock OK: title={str(script.get('title'))[:60]!r}")
    return script