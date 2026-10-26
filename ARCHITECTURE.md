# Architecture

## Overview

```
Client (curl/Postman)
    │
    ▼
POST /api/v1/jobs  { "query": "..." }  ──► JobStore (in-memory dict)  status=PENDING
    │                                        │
    ▼                                        ▼
BackgroundTasks → run_pipeline(job_id)   status=RUNNING
    │
    ├─ 1. Load knowledge  (YAML theo query — src/knowledge/)
    ├─ 2. Generate script (Gemini → validate → retry → mock fallback)
    ├─ 3. Quality gate    (schema + content checks — src/services/quality.py)
    ├─ 4. Generate visual (Pillow slides + matplotlib chart)
    ├─ 5. TTS             (edge-tts theo từng phần → concat ffmpeg)
    ├─ 6. Assemble        (ffmpeg concat: slides + audio → lesson.mp4)
    └─ 7. Final check → status=COMPLETED / FAILED
    │
    ▼
GET /api/v1/jobs/{job_id}  → { status, progress, result, artifacts }
```

## Boundaries

| Layer              | Responsibility                                  | Tech / Vị trí                       |
|-------------------|--------------------------------------------------|--------------------------------------|
| API               | Routes, schema validation, job create/poll     | FastAPI + Pydantic — `api/`          |
| Domain / Pipeline | Các bước pipeline, quality gate, retry          | `src/pipeline/`, `src/services/`    |
| Persistence       | In-memory job store + artifacts trên đĩa        | dict + lock (`src/store/memory.py`), `outputs/{job_id}/` |
| External providers| LLM, TTS, media                                   | Gemini / edge-tts / ffmpeg (có fallback) |

## Job Lifecycle

```
PENDING → RUNNING → (loading_knowledge → generating_script → quality_gate
                      → generating_visual → generating_audio → assembling)
          → COMPLETED
          ↘ FAILED (error + partial artifacts nếu có)
```

- `POST /jobs` tạo job + trả `job_id` **ngay lập tức** (202); pipeline chạy trong `BackgroundTasks`.
- `GET /jobs/{id}` poll `status` + `progress` (tên bước đang chạy) + `result` khi COMPLETED.
- Store là dict trong RAM với `threading.Lock` — mọi create/get/update thread-safe. **Restart = mất job** (chấp nhận được cho prototype).

## Persistence / Artifact boundary

- **Job state** (status, progress, error) sống trong RAM (`src/store/memory.py`) — không DB, không auth.
- **Artifacts** (files thật) viết xuống đĩa dưới `outputs/{job_id}/`:

  ```
  outputs/{job_id}/
  ├── images/   slide_00.png ... slide_NN.png (+ chart.png)
  ├── audio/    part_*.mp3 (từng phần) + narration.mp3 (đã concat)
  └── final/    lesson.mp4 (slideshow + narration)
  ```

- `result.artifacts` trong response chỉ chứa **path** tới các file này. API không serve file — client đọc trực tiếp từ đĩa.
- Tạo `outputs/`, `logs/` tự động khi import config (`src/config.py::ensure_dirs`).

## AI / Video-generation boundary

Tác nhân non-deterministic tách khỏi logic qua interface, **mỗi bước đều có mock path** — demo không hard-fail vì provider lỗi:

| Bước     | Provider thật               | Retry | Fallback                                        |
|----------|------------------------------|-------|--------------------------------------------------|
| Script    | Gemini (`src/llm/client.py`, model `gemini-2.5-flash`) | `MAX_RETRIES` lần, timeout `TIMEOUT_SECONDS` | `mock_script` từ knowledge YAML (`src/knowledge/loader.py::get_mock_script`) |
| Validate  | Pydantic/quality gate       | —     | Validate fail hết retry → force mock + validate lại |
| Visual    | Pillow + matplotlib (pure function) | — | Không cần — deterministic                        |
| TTS       | edge-tts (voice `en-US-AriaNeural`), **từng phần một** (title/section/summary) | `MAX_RETRIES`/phần | Concat ffmpeg; mọi phần fail → silent mp3       |
| Video     | ffmpeg concat demuxer + aac  | —     | Không có ffmpeg trong PATH → bỏ video, vẫn trả slides + audio |

**Lưu ý TTS:** không gộp cả script thành 1 khối text cho edge-tts — text dài làm thư viện split nội bộ và gây audio lặp. Mỗi phần text ngắn được generate riêng rồi concat.

**Lưu ý Assembler:** đo duration audio bằng ffprobe rồi chia đều `per_slide = audio_dur / n_slides` để video dài bằng/hơn audio — **không dùng `-shortest`** (sẽ cắt mất giọng đọc cuối).

## Trade-offs

- **In-memory store** thay vì Redis/DB — zero infra, đủ cho prototype; mất khi restart.
- **BackgroundTasks** thay vì Celery — không cần broker; đủ cho 3 query demo.
- **Mock fallback mạnh** — ưu tiên demo luôn chạy ổn định hơn nội dung "thật" 100%.
- **Visual đơn giản** (slide tĩnh + 1 chart) — ưu tiên correctness + giá trị giáo dục.

## Logging

Mọi module dùng `src/logger.py::get_formatted_logger` (không `print`). Pipeline log từng bước với thời gian (`src/pipeline/timing.py`): `STEP START → STEP DONE (X.XXs) | detail`, kèm raw LLM response (300 chars) và ffmpeg command khi `LOG_LEVEL=DEBUG`.