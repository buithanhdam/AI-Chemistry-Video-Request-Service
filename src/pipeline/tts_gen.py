"""TTS step: edge-tts theo từng phần + concat ffmpeg + fallback silent."""
import asyncio
from pathlib import Path
from typing import Optional

from src.config import settings
from src.logger import get_formatted_logger

logger = get_formatted_logger("tts_gen")

VOICE = "en-US-AriaNeural"

    
def _script_chunks(script: dict) -> list[tuple[str, str]]:
    """Chia script thành các phần nhỏ (không gộp 1 khối lớn tránh bug edge-tts)."""
    chunks: list[tuple[str, str]] = []
    title = str(script.get("title", "")).strip()
    if title:
        chunks.append(("part_00_title", f"{title}."))
    for i, section in enumerate(script.get("sections", []), start=1):
        text = []
        heading = str(section.get("heading", "")).strip()
        if heading:
            text.append(f"{heading}.")
        narration = str(section.get("narration", "")).strip()
        if narration:
            text.append(narration)
        if text:
            chunks.append((f"part_{i:02d}", " ".join(text)))
    summary = str(script.get("summary", "")).strip()
    if summary:
        chunks.append((f"part_{len(chunks):02d}_summary", f"Summary. {summary}"))
    return chunks


async def _tts_chunk(text: str, out_path: Path, attempt: int) -> bool:
    """Generate 1 phần. Return True nếu file OK."""
    t0 = asyncio.get_event_loop().time()
    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, VOICE)
        await asyncio.wait_for(
            communicate.save(str(out_path)),
            timeout=settings.TIMEOUT_SECONDS * 2,
        )
        size = out_path.stat().st_size if out_path.exists() else 0
        if size > 0:
            logger.info(
                f"TTS {out_path.name} OK (attempt={attempt}, "
                f"{asyncio.get_event_loop().time() - t0:.1f}s): size={size // 1024}KB"
            )
            return True
        logger.warning(f"TTS {out_path.name} (attempt={attempt}): file rỗng")
        return False
    except Exception as exc:
        logger.warning(
            f"TTS {out_path.name} fail (attempt={attempt}, "
            f"{asyncio.get_event_loop().time() - t0:.1f}s): {exc}"
        )
        return False


def _concat_mp3(paths: list[Path], out_path: Path) -> bool:
    """Ghép các mp3 (cùng codec) thành 1 file bằng concat demuxer."""
    import subprocess

    list_file = out_path.parent / "concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p.as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:a", "libmp3lame", "-b:a", "128k",
        str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=60)
    if proc.returncode == 0 and out_path.exists():
        logger.info(f"TTS concat OK: {len(paths)} parts -> {out_path.name}")
        return True
    logger.warning(
        f"TTS concat fail rc={proc.returncode}: "
        f"{proc.stderr.decode(errors='replace')[-300:]}"
    )
    return False


def _silent_audio(out_path: Path, seconds: float = 6.0) -> bool:
    """Fallback: mp3 im lặng."""
    try:
        import io
        import struct
        import subprocess
        import wave

        rate = 24000
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            n = int(rate * seconds)
            wf.writeframes(struct.pack("<" + "h" * n, *([0] * n)))

        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", "pipe:0", "-codec:a", "libmp3lame", str(out_path)],
            input=buf.getvalue(), capture_output=True,
            timeout=settings.TIMEOUT_SECONDS,
        )
        return proc.returncode == 0 and out_path.exists()
    except Exception as exc:
        logger.error(f"Silent audio fallback fail: {exc}")
        return False


async def generate_audio(script: dict, out_dir: Path) -> Optional[str]:
    """Generate narration theo từng phần → concat. Trả path narration.mp3 hoặc None."""
    audio_dir = out_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / "narration.mp3"

    chunks = _script_chunks(script)
    if not chunks:
        logger.error("TTS: script rỗng, không có gì để đọc")
        return None
    logger.info(f"TTS start: {len(chunks)} chunks")

    part_paths: list[Path] = []
    for name, text in chunks:
        part_path = audio_dir / f"{name}.mp3"
        ok = False
        for attempt in range(1, max(1, settings.MAX_RETRIES) + 1):
            if await _tts_chunk(text, part_path, attempt):
                ok = True
                break
            await asyncio.sleep(1)
        if not ok:
            logger.warning(f"TTS: bỏ phần {name} (fail hết retry)")
        elif part_path.stat().st_size > 0:
            part_paths.append(part_path)

    if part_paths:
        if _concat_mp3(part_paths, out_path):
            return str(out_path)
        # Concat fail → thử dùng trực tiếp 1 file duy nhất nếu chỉ có 1 part
        if len(part_paths) == 1:
            import shutil

            shutil.copy2(part_paths[0], out_path)
            logger.warning(f"TTS: dùng thẳng 1 part duy nhất -> {out_path.name}")
            return str(out_path)

    logger.warning("TTS hết mọi đường → fallback silent audio")
    if _silent_audio(out_path):
        logger.info(f"TTS fallback silent: {out_path}")
        return str(out_path)

    logger.error("TTS fail hoàn toàn (kể cả silent fallback)")
    return None