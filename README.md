# Chemistry Learner — AI Chemistry Video Request Service

Async job API (FastAPI) sinh bài học hoá học multimodal (slides + giọng đọc + video) cho **3 query bắt buộc**, reliability-first: mọi bước non-deterministic đều có retry + mock fallback.

## Supported queries

1. `How does the pH scale work?`
2. `Why do atoms form covalent bonds?`
3. `What is the difference between ionic and covalent bonding?`

## Quick start

```bash
# 1. System deps: ffmpeg + ffprobe phải có trong PATH
#    (dùng để ghép slides + audio thành video và đo duration)

# Windows (winget — khuyến nghị):
winget install --id Gyan.FFmpeg
#   → mở lại terminal, kiểm tra: ffmpeg -version
#    hoặc tải build từ https://www.gyan.dev/ffmpeg/builds/ và thêm bin/ vào PATH

# Linux (Debian/Ubuntu):
sudo apt update && sudo apt install -y ffmpeg

# macOS (Homebrew):
brew install ffmpeg

# Kiểm tra cài đặt xong:
ffmpeg -version && ffprobe -version

# 2. Venv
python -m venv venv
venv\Scripts\activate        # Windows  (source venv/bin/activate trên Linux/macOS)

# 3. Deps
pip install -r requirements.txt

# 4. Config
copy .env.example .env        # điền GEMINI_API_KEY (optional; không có key → dùng mock)

# 5. Run
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Server tự tạo `outputs/`, `logs/` khi khởi động (xem `src/config.py::ensure_dirs`).

## API

| Method | Endpoint                       | Mô tả                                   |
|--------|--------------------------------|------------------------------------------|
| POST   | `/api/v1/jobs`                 | Tạo job, trả `job_id` ngay (202)         |
| GET    | `/api/v1/jobs/{job_id}`        | Poll status/progress/result              |
| GET    | `/api/v1/jobs?job_id=...`      | Như trên, kiểu query param               |
| GET    | `/health`                      | Health check                             |

**POST /api/v1/jobs**

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"query": "How does the pH scale work?"}'

# → 202 {"job_id": "job_abc12345", "status": "PENDING", "created_at": "..."}
```

**GET /api/v1/jobs/{job_id}**

```json
{
  "job_id": "job_abc12345",
  "status": "COMPLETED",
  "query": "How does the pH scale work?",
  "progress": "assembled",
  "result": {
    "script": { "title": "...", "sections": [...], "summary": "..." },
    "artifacts": {
      "slides": ["outputs/job_abc12345/images/slide_00.png", "..."],
      "audio": ["outputs/job_abc12345/audio/narration.mp3"],
      "final_video": "outputs/job_abc12345/final/lesson.mp4"
    }
  },
  "error": null
}
```

Status: `PENDING → RUNNING → COMPLETED | FAILED`. Errors: `404` job không tồn tại, `422` query rỗng/quá dài (5–300 ký tự).

## Test

```bash
# End-to-end chạy 3 query bắt buộc qua HTTP (cần server đang chạy)
bash scripts/demo.sh        # hoặc: python -m pytest tests/ -v (nếu có pytest)

# Smoke test trong repo
python -c "from fastapi.testclient import TestClient; from main import app; \
c = TestClient(app); print(c.get('/health').json())"
```

**Demo 3 query end-to-end:** `scripts/demo.sh` (curl) tạo 3 job, poll tới COMPLETED và in artifacts.

## Best generated videos

Ba video tốt nhất của learner nằm ở `outputs/{job}/final/lesson.mp4`:

- pH scale: `outputs/<job>/final/lesson.mp4` (query 1)
- Covalent bonds: `outputs/<job>/final/lesson.mp4` (query 2)
- Ionic vs covalent: `outputs/<job>/final/lesson.mp4` (query 3)

> Lưu ý: repo không commit artifacts (`.gitignore` bỏ `outputs/`, `logs/`); chạy demo để tái sinh. Video gồm slideshow slides (Pillow + matplotlib) + narration edge-tts, độ dài video được canh theo audio để không mất tiếng.

## Design decisions

- **In-memory store + BackgroundTasks** — đơn giản, zero infra, đủ cho prototype
- **Mock fallback mọi bước** — demo không bao giờ hard-fail vì Gemini/edge-tts lỗi
- **Retry + timeout cấu hình qua `.env`** — dễ tune khi demo
- **TTS theo từng phần** — tránh bug edge-tts với text dài bị lặp audio

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md).