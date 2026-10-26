"""Pipeline runner: orchestrate knowledge → script → quality → visual → TTS → assemble."""
import time

from src.config import settings
from src.knowledge.loader import get_knowledge
from src.logger import get_formatted_logger
from src.models.job import JobStatus
from src.pipeline.assembler import assemble
from src.pipeline.script_gen import generate_script
from src.pipeline.timing import step_timer
from src.pipeline.tts_gen import generate_audio
from src.pipeline.visual_gen import generate_visuals
from src.store.memory import job_store

logger = get_formatted_logger("pipeline.runner")


async def run_pipeline(job_id: str) -> None:
    """Background task: chạy toàn bộ pipeline cho 1 job, update store từng bước."""
    started = time.perf_counter()
    job = job_store.get(job_id)
    if not job:
        logger.error(f"Pipeline: job không tồn tại {job_id}")
        return

    query = job.query
    out_dir = settings.output_path / job_id
    logger.info(f"[{job_id}] PIPELINE START: query={query[:80]!r} out_dir={out_dir}")

    def log(msg: str) -> None:
        logger.info(msg)

    def _fail(error: str) -> None:
        logger.error(f"[{job_id}] PIPELINE FAILED: {error}")
        job_store.update(job_id, status="FAILED", error=error)

    try:
        # 1. Load knowledge
        job_store.update(job_id, status="RUNNING", progress="loading_knowledge")
        with step_timer(job_id, "1/6 load_knowledge", log):
            knowledge = get_knowledge(query)
        if knowledge is None:
            _fail(f"Không tìm thấy knowledge base cho query: {query[:100]}")
            return
        log(f"[{job_id}]   knowledge={knowledge.get('title', '?')!r}")

        # 2. Script generation (LLM retry + validate + mock fallback)
        job_store.update(job_id, progress="generating_script")
        with step_timer(job_id, "2/6 generate_script (LLM)", log) as t:
            script = await generate_script(query, knowledge)
            t["detail"] = (
                f"sections={len(script.get('sections', []))} "
                f"title={str(script.get('title', ''))[:40]!r}"
            )

        # 3. Quality gate
        job_store.update(job_id, progress="quality_gate")
        with step_timer(job_id, "3/6 quality_gate", log):
            from src.services.quality import validate_script

            validate_script(script)

        # 4. Visual generation
        job_store.update(job_id, progress="generating_visual")
        with step_timer(job_id, "4/6 generate_visuals (Pillow/matplotlib)", log) as t:
            slides = await generate_visuals(query, script, out_dir)
            t["detail"] = f"slides={len(slides)}"
        if not slides:
            _fail("Visual generation trả về rỗng")
            return

        # 5. TTS (edge-tts)
        job_store.update(job_id, progress="generating_audio")
        with step_timer(job_id, "5/6 generate_audio (edge-tts)", log) as t:
            audio_path = await generate_audio(script, out_dir)
            t["detail"] = f"path={audio_path}" if audio_path else "fallback=none"
        if audio_path:
            try:
                size_kb = (out_dir / "audio" / "narration.mp3").stat().st_size // 1024
                log(f"[{job_id}]   audio size={size_kb}KB")
            except OSError:
                pass

        # 6. Assemble (ffmpeg)
        job_store.update(job_id, progress="assembling")
        with step_timer(job_id, "6/6 assemble (ffmpeg)", log) as t:
            final_video = await assemble(slides, audio_path, out_dir)
            t["detail"] = f"video={final_video}" if final_video else "video=skipped"

        # 7. Final check + update status
        artifacts = {
            "slides": slides,
            "audio": [audio_path] if audio_path else [],
            "final_video": final_video,
        }
        if not audio_path and not final_video:
            _fail("Pipeline không tạo được audio lẫn video")
            return

        job_store.update(
            job_id,
            status="COMPLETED",
            progress="assembled",
            result={"script": script, "artifacts": artifacts},
        )
        elapsed = time.perf_counter() - started
        logger.info(
            f"[{job_id}] PIPELINE COMPLETED ({elapsed:.1f}s) "
            f"slides={len(slides)} audio={bool(audio_path)} video={bool(final_video)}"
        )
    except Exception as exc:
        logger.exception(f"[{job_id}] Unhandled pipeline error")
        _fail(f"Pipeline error: {exc}")