"""Assembler: ghép slides + audio thành video bằng ffmpeg."""
import asyncio
from pathlib import Path
from typing import Optional

from src.config import settings
from src.logger import get_formatted_logger

logger = get_formatted_logger("assembler")


def _ffmpeg_available() -> bool:
    import shutil

    return shutil.which("ffmpeg") is not None

def _has_audio_stream(path: str) -> bool:
    import subprocess
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, timeout=15,
        )
        return b"audio" in proc.stdout
    except (subprocess.TimeoutExpired, OSError):
        return False
    
    
def _audio_duration(audio: Optional[str]) -> Optional[float]:
    """Đo độ dài audio (giây) bằng ffprobe. None nếu fail."""
    import subprocess

    if not audio or not Path(audio).exists():
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio),
            ],
            capture_output=True,
            timeout=15,
        )
        return float(proc.stdout.decode(errors="replace").strip())
    except (ValueError, subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"Không đo được audio duration: {exc}")
        return None


def _assemble_sync(slides: list[str], audio: Optional[str], out_dir: Path) -> Optional[str]:
    if not slides:
        logger.warning("Assembler: không có slides")
        return None
    if not _ffmpeg_available():
        logger.warning("Assembler: ffmpeg không có trong PATH → bỏ video")
        return None

    final_dir = out_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    out_path = final_dir / "lesson.mp4"

    audio_path = Path(audio).resolve() if audio and Path(audio).exists() else None
    audio_dur = _audio_duration(str(audio_path)) if audio_path else None
    images = [s for s in slides if s.lower().endswith((".png", ".jpg"))]
    n = len(images)

    # Ưu tiên chia đều theo độ dài audio thật để không cắt mất giọng đọc.

    if audio_dur and audio_dur > 0:
        per_slide = audio_dur / n
        logger.debug(f"Audio duration={audio_dur:.1f}s → per_slide={per_slide:.1f}s")
    else:
        per_slide = max(2.0, 20.0 / n)
        logger.warning(
            f"Không có audio duration → dùng per_slide mặc định {per_slide:.1f}s"
        )

    concat_file = final_dir / "concat.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for slide in images:
            p = Path(slide).resolve().as_posix().replace("'", r"'\''")
            f.write(f"file '{p}'\n")
            f.write(f"duration {per_slide}\n")
        if images:
            p = Path(images[-1]).resolve().as_posix().replace("'", r"'\''")
            f.write(f"file '{p}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    if audio_path:
        cmd += ["-i", str(audio_path)]
    cmd += [
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p",
    ]
    if audio_path:
        cmd += [
            "-map", "0:v:0", "-map", "1:a:0",      # map tường minh
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        ]
    cmd += ["-movflags", "+faststart", str(out_path)]

    import subprocess
    import time as _time

    logger.debug(f"ffmpeg cmd: {' '.join(cmd)}")
    t0 = _time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=max(120, settings.TIMEOUT_SECONDS * 4),
            cwd=str(out_dir),
        )
    except subprocess.TimeoutExpired:
        logger.warning("Assembler: ffmpeg timeout")
        return None

    elapsed = _time.perf_counter() - t0
    if proc.returncode != 0 or not out_path.exists():
        logger.warning(
            f"Assembler: ffmpeg fail rc={proc.returncode} ({elapsed:.1f}s): "
            f"{proc.stderr.decode(errors='replace')[-500:]}"
        )
        return None

    # Final check: video phải dài >= audio để không mất tiếng
    video_dur = _audio_duration(str(out_path))
    size_kb = out_path.stat().st_size // 1024
    logger.info(
        f"Assembler OK ({elapsed:.1f}s): {out_path} size={size_kb}KB "
        f"slides={n} per_slide={per_slide:.1f}s "
        f"audio_dur={audio_dur and f'{audio_dur:.1f}s'} video_dur={video_dur and f'{video_dur:.1f}s'}"
    )
    if audio_dur and video_dur and video_dur < audio_dur - 1:
        logger.warning(
            f"Assembler: video ({video_dur:.1f}s) ngắn hơn audio ({audio_dur:.1f}s) → "
            f"có thể mất tiếng cuối!"
        )
    return str(out_path)


async def assemble(slides: list[str], audio: Optional[str], out_dir: Path) -> Optional[str]:
    return await asyncio.to_thread(_assemble_sync, slides, audio, out_dir)