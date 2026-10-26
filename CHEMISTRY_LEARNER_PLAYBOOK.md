# PLAYBOOK — Chemistry Learner Prototype (Async Job + Multimodal Artifacts)

**Timebox:** 90–120 phút  
**Stack:** FastAPI (BackgroundTasks) · In-memory store · Gemini (free tier) + mock fallback · edge-tts · Pillow · matplotlib · ffmpeg + mediapy  
**Goal:** End-to-end job API cho 3 query bắt buộc, reliability-first (retry/fallback/validation), visual đơn giản nhưng đủ giáo dục.

---

## 0. Checklist tổng quan

### Trước session
- [ ] Cài ffmpeg (`sudo apt install ffmpeg` hoặc tương đương)
- [ ] Tạo project folder + venv
- [ ] Chuẩn bị `.env` (GEMINI_API_KEY optional, MAX_RETRIES, TIMEOUT)
- [ ] Chuẩn bị knowledge base YAML (pH, bonding, elements)
- [ ] Mở terminal + Postman/curl sẵn
- [ ] Ghi lại 3 query bắt buộc

### Trong session
- [ ] 0–10': đọc brief + chốt architecture + boundaries
- [ ] 10–25': scaffold project + models + in-memory store + job routes
- [ ] 25–45': core pipeline (script gen → validate → visual → TTS → assemble)
- [ ] 45–70': retry/fallback + quality gate + knowledge base
- [ ] 70–95': 3 query end-to-end + demo script
- [ ] 95–110': README + ARCHITECTURE + polish
- [ ] 110–120': final test + commit

### Deliverables
- [ ] Repo chạy được với `uvicorn main:app --reload`
- [ ] 3 query end-to-end trả về artifacts (images + audio + final video/json)
- [ ] README.md + ARCHITECTURE.md đầy đủ
- [ ] Demo script (curl) trong `scripts/demo.sh`
- [ ] Knowledge base YAML trong `src/knowledge/`

---

## 1. Tóm tắt yêu cầu từ brief

### Must-have
- API job lifecycle: `POST /jobs` → trả job_id ngay → `GET /jobs/{id}` poll status + result
- Background task chạy pipeline agent
- Hỗ trợ **đúng 3 query** end-to-end:
  1. How does the pH scale work?
  2. Why do atoms form covalent bonds?
  3. What is the difference between ionic and covalent bonding?
- Pipeline: script generation (LLM hoặc mock) → validate → visual slides (Pillow/matplotlib) → TTS (edge-tts) → cắt ghép (ffmpeg/mediapy) → artifacts
- Retry + timeout + fallback mock cho mọi non-deterministic step
- Output structured JSON + artifacts (images, audio, final video nếu có)
- In-memory store (dict + lock)

### Scope bắt buộc
- FastAPI + BackgroundTasks
- In-memory job store
- Gemini free tier (nếu có key) → fallback mock
- edge-tts + Pillow + matplotlib + ffmpeg
- Knowledge base chemistry (YAML)
- 3 query cố định phải chạy ổn

### Được phép simplify / mock
- Visual: slide đơn giản (text + basic shape/chart) bằng Pillow/matplotlib, **không** animate phức tạp
- LLM: nếu fail → dùng template/mock script có sẵn cho 3 query
- Video: có thể chỉ xuất slideshow + audio, hoặc 1 video đơn giản
- Không cần UI, không cần auth, không cần persistent DB

### Tiêu chí đánh giá chính (suy ra từ note)
- Reliability (retry/fallback/validation)
- Clean job API + lifecycle
- Visual đủ dữ liệu giáo dục
- End-to-end 3 query chạy được

---

## 2. Kiến trúc đề xuất

### Sơ đồ text end-to-end
```
Client (curl/Postman)
    │
    ▼
POST /api/v1/jobs  { "query": "..." }
    │
    ▼
JobStore (in-memory dict)  ← tạo job_id, status=PENDING
    │
    ▼
BackgroundTasks → run_pipeline(job_id)
    │
    ├─ 1. Load knowledge (YAML)
    ├─ 2. Generate script (Gemini → validate → retry → mock fallback)
    ├─ 3. Quality gate (structured check)
    ├─ 4. Generate visuals (Pillow slides + matplotlib charts)
    ├─ 5. TTS (edge-tts) → audio files
    ├─ 6. Assemble (ffmpeg/mediapy) → final artifacts
    ├─ 7. Final check + update status=COMPLETED / FAILED
    │
    ▼
GET /api/v1/jobs/{job_id}  → {status, progress, result, artifacts}
```

### Lifecycle
```
PENDING → RUNNING → (VALIDATING → GENERATING_VISUAL → GENERATING_AUDIO → ASSEMBLING) → COMPLETED
                                                                  ↘ FAILED (với error + partial artifacts nếu có)
```

### Boundaries
| Layer              | Responsibility                          | Tech                     |
|--------------------|-----------------------------------------|--------------------------|
| API                | Routes, schemas, validation, job create | FastAPI + Pydantic       |
| Domain / Logic     | Pipeline steps, quality gate, retry     | `src/services/`, `src/pipeline/` |
| Persistence        | In-memory job store + artifacts folder  | dict + `outputs/{job_id}/` |
| External providers | LLM, TTS, media                         | Gemini / edge-tts / ffmpeg (có fallback) |

### Trade-off đã chọn
- **In-memory store** thay vì Redis/DB → đủ cho prototype, zero infra.
- **BackgroundTasks** thay vì Celery → đơn giản, không cần broker.
- **Mock fallback mạnh** → demo luôn ổn định dù Gemini rate-limit / fail.
- **Visual đơn giản** → ưu tiên correctness + giáo dục hơn đẹp.
- **Retry config từ .env** → dễ tune khi demo.

---

## 3. Cấu trúc project

```
project-root/
├── main.py                 # FastAPI app + lifespan
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   └── jobs.py         # POST /jobs, GET /jobs/{id}
│   ├── schemas.py          # Request/Response models
│   └── deps.py             # get_job_store
├── src/
│   ├── __init__.py
│   ├── config.py           # Settings từ .env
│   ├── logger.py
│   ├── models/
│   │   └── job.py          # Domain Job model + Status enum
│   ├── store/
│   │   └── memory.py       # InMemoryJobStore
│   ├── knowledge/
│   │   ├── ph_scale.yaml
│   │   ├── covalent_bonds.yaml
│   │   └── ionic_vs_covalent.yaml
│   ├── llm/
│   │   ├── client.py       # Gemini wrapper + mock
│   │   └── prompts.py
│   ├── pipeline/
│   │   ├── runner.py       # Orchestrator
│   │   ├── script_gen.py
│   │   ├── visual_gen.py
│   │   ├── tts_gen.py
│   │   └── assembler.py
│   └── services/
│       └── quality.py      # Validation + quality gate
├── outputs/                # artifacts theo job_id
├── scripts/
│   └── demo.sh
├── logs/
├── tests/
├── .env.example
├── requirements.txt
├── README.md
└── ARCHITECTURE.md
```

**Vai trò**
- `api/`: HTTP boundary, schema validation
- `src/models` + `src/store`: domain + persistence
- `src/pipeline/*`: từng bước có retry/fallback riêng
- `src/knowledge/`: YAML knowledge base (source of truth cho mock + context)
- `outputs/{job_id}/`: images/, audio/, final/

**Import convention**
```python
from src.config import settings
from src.store.memory import job_store
from src.pipeline.runner import run_pipeline
```

**Lệnh chạy**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

## 4. Setup từ số 0

```bash
# System
sudo apt update && sudo apt install -y ffmpeg

# Project
mkdir -p chemistry-learner && cd chemistry-learner
python -m venv .venv
source .venv/bin/activate

# requirements.txt

fastapi==0.115.0
uvicorn[standard]==0.30.6

pydantic==2.9.2
pydantic-settings==2.5.2
python-dotenv==1.0.1

google-genai==1.38.0

edge-tts==6.1.12
Pillow==10.4.0
matplotlib==3.9.2
mediapy==1.2.2
PyYAML==6.0.2

httpx>=0.28.1


pip install -r requirements.txt
```

**.env.example**
```env
GEMINI_API_KEY=
MAX_RETRIES=3
TIMEOUT_SECONDS=30
OUTPUT_DIR=outputs
LOG_LEVEL=INFO
```

**main.py skeleton**
```python
from fastapi import FastAPI
from api.routes import jobs
from src.config import settings
from src.logger import setup_logger

setup_logger()
app = FastAPI(title="Chemistry Learner Prototype", version="0.1.0")
app.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
```

---

## 5. API contract

### POST /api/v1/jobs
**Request**
```json
{
  "query": "How does the pH scale work?"
}
```
**Response 202**
```json
{
  "job_id": "job_abc123",
  "status": "PENDING",
  "created_at": "2025-..."
}
```

### GET /api/v1/jobs/{job_id}
**Response 200**
```json
{
  "job_id": "job_abc123",
  "status": "COMPLETED",
  "query": "How does the pH scale work?",
  "progress": "assembled",
  "result": {
    "script": { ... },
    "artifacts": {
      "slides": ["outputs/job_abc123/images/slide_01.png", ...],
      "audio": ["outputs/job_abc123/audio/narration.mp3"],
      "final_video": "outputs/job_abc123/final/lesson.mp4"
    }
  },
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

**Errors**
- 404: job not found
- 422: invalid query (empty / quá dài)

---

## 6. Data models

```python
# api/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class CreateJobRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=300)

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    query: str
    progress: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

# src/models/job.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class Job:
    job_id: str
    query: str
    status: JobStatus = JobStatus.PENDING
    progress: str = "queued"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
```

---

## 7. State / store / background flow

```python
# src/store/memory.py
from threading import Lock
from typing import Dict, Optional
from src.models.job import Job
from datetime import datetime

class InMemoryJobStore:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = Lock()

    def create(self, job: Job) -> Job:
        with self._lock:
            self._jobs[job.job_id] = job
            return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = datetime.utcnow()
            return job

job_store = InMemoryJobStore()
```

**API route pattern**
```python
@router.post("/jobs", status_code=202)
async def create_job(req: CreateJobRequest, background_tasks: BackgroundTasks):
    job_id = f"job_{uuid4().hex[:8]}"
    job = Job(job_id=job_id, query=req.query)
    job_store.create(job)
    background_tasks.add_task(run_pipeline, job_id)
    return JobResponse(...)
```

---

## 8. Pipeline / business logic chính

Thứ tự trong `src/pipeline/runner.py`:

1. **Load knowledge** theo query (map 3 query → YAML file)
2. **Generate script** (`script_gen.py`)
   - Call Gemini với structured prompt
   - Validate schema (title, sections[], key_points[], narration_text)
   - Retry tối đa `MAX_RETRIES` (timeout từ config)
   - Fallback → mock script từ knowledge YAML
3. **Quality gate** (`services/quality.py`)
   - Check length, required keys, no empty sections
   - Nếu fail → force mock
4. **Visual gen** (`visual_gen.py`)
   - Pillow: text slides (title + bullet)
   - matplotlib: pH scale chart / bonding diagram đơn giản
   - Save `outputs/{job_id}/images/slide_XX.png`
5. **TTS** (`tts_gen.py`)
   - edge-tts với narration_text
   - Save `outputs/{job_id}/audio/narration.mp3`
6. **Assemble** (`assembler.py`)
   - mediapy / ffmpeg: slideshow + audio → `final/lesson.mp4` (hoặc chỉ zip artifacts nếu timebox gắt)
7. **Final check** + update status COMPLETED / FAILED

**Boundary thay provider**
- LLM: `src/llm/client.py` → interface `generate(prompt) -> dict`
- TTS: wrapper quanh edge-tts
- Visual: pure function nhận script → list path images

---

## 9. Prompt / schema cho LLM

**Prompt mẫu** (trong `src/llm/prompts.py`)
```text
You are a chemistry educator. Given the learner query and knowledge base, generate a short educational script.

Query: {query}
Knowledge:
{knowledge_yaml}

Return ONLY valid JSON matching this schema:
{
  "title": "string",
  "sections": [
    {
      "heading": "string",
      "key_points": ["string", ...],
      "narration": "string (2-4 sentences, spoken style)"
    }
  ],
  "summary": "string"
}
```

**Retry khi validate fail**
```python
for attempt in range(settings.MAX_RETRIES):
    try:
        raw = await llm_client.generate(...)
        data = json.loads(raw)
        ScriptSchema.model_validate(data)  # Pydantic
        return data
    except Exception as e:
        logger.warning(f"Attempt {attempt+1} failed: {e}")
        await asyncio.sleep(1)
return get_mock_script(query)  # fallback
```

---

## 10. Hướng dẫn dùng AI coding agent

### Nguyên tắc hybrid
- **Bạn (human)**: chốt architecture, boundaries, thứ tự pipeline, quality criteria, quyết định mock vs real.
- **Agent**: implement từng file/task nhỏ, không tự mở rộng scope.

### Prompt khởi động agent
```
Bạn là coding agent. Project FastAPI chemistry learner prototype.
Cấu trúc đã chốt trong ARCHITECTURE.md và Playbook.
Chỉ implement đúng task tôi giao. Không thêm feature. Không refactor ngoài task.
Dùng đúng import convention và folder structure.
Khi xong task, chạy thử nếu có thể và báo kết quả ngắn.
```

### Danh sách task nhỏ (copy-paste)

1. **Scaffold**  
   Tạo toàn bộ folder structure + `main.py` + `requirements.txt` + `.env.example` + `src/config.py` + `src/logger.py`.

2. **Models + Store**  
   Implement `src/models/job.py` + `src/store/memory.py` (thread-safe).

3. **API schemas + routes**  
   `api/schemas.py` + `api/routes/jobs.py` (POST + GET) + wire vào `main.py`. Dùng BackgroundTasks.

4. **Config + knowledge loader**  
   `src/config.py` (pydantic-settings) + load 3 file YAML trong `src/knowledge/`.

5. **LLM client + mock**  
   `src/llm/client.py` + `prompts.py`. Có `generate()` + fallback mock cho 3 query.

6. **Script generation step**  
   `src/pipeline/script_gen.py` với retry + validate + fallback.

7. **Quality gate**  
   `src/services/quality.py` — check schema + content tối thiểu.

8. **Visual gen**  
   `src/pipeline/visual_gen.py` — Pillow slides + 1 matplotlib chart (pH scale hoặc bonding).

9. **TTS step**  
   `src/pipeline/tts_gen.py` dùng edge-tts.

10. **Assembler**  
    `src/pipeline/assembler.py` — ghép images + audio (ffmpeg hoặc mediapy).

11. **Pipeline runner**  
    `src/pipeline/runner.py` — orchestrate 1→6, update progress + status.

12. **Demo script + 3 query test**  
    `scripts/demo.sh` + chạy end-to-end 3 query.

13. **README + ARCHITECTURE**  
    Viết 2 file theo mục 13 & 14.

14. **Final polish**  
    Error handling, log rõ, đảm bảo artifacts path đúng.

### Cách xử lý khi agent sai
- Bảo: “Chỉ sửa file X, không đụng file khác.”
- Nếu hallucinate import → paste đúng skeleton.
- Nếu scope creep → “Revert phần ngoài task, chỉ giữ đúng yêu cầu.”

---

## 11. Fallback / template / knowledge

**Knowledge base** (ví dụ `src/knowledge/ph_scale.yaml`)
```yaml
title: "How the pH Scale Works"
key_concepts:
  - "pH measures acidity/basicity from 0 to 14"
  - "pH 7 is neutral (pure water)"
  - "Below 7 acidic, above 7 basic"
  - "Each unit is 10x change in H+ concentration"
mock_script:
  title: "Understanding the pH Scale"
  sections:
    - heading: "What is pH?"
      key_points: ["pH = potential of Hydrogen", "Scale 0–14"]
      narration: "The pH scale measures how acidic or basic a solution is..."
  summary: "pH is a logarithmic scale of hydrogen ion concentration."
```

Tương tự cho 2 query còn lại.  
Khi LLM fail → trả thẳng `mock_script`.

---

## 12. Demo script

```bash
#!/bin/bash
# scripts/demo.sh
BASE=http://localhost:8000/api/v1

echo "=== 1. pH Scale ==="
JOB1=$(curl -s -X POST $BASE/jobs -H "Content-Type: application/json" \
  -d '{"query":"How does the pH scale work?"}' | jq -r .job_id)
echo "Job: $JOB1"
sleep 2
curl -s $BASE/jobs/$JOB1 | jq .

echo "=== 2. Covalent bonds ==="
JOB2=$(curl -s -X POST $BASE/jobs -H "Content-Type: application/json" \
  -d '{"query":"Why do atoms form covalent bonds?"}' | jq -r .job_id)
echo "Job: $JOB2"
# ... poll tương tự

echo "=== 3. Ionic vs Covalent ==="
# tương tự
```

---

## 13. Nội dung bắt buộc README.md

```markdown
# Chemistry Learner Prototype

Async job API that generates educational multimodal lessons for 3 fixed chemistry queries.

## Quick start
...
## API
POST /api/v1/jobs
GET /api/v1/jobs/{job_id}

## Supported queries
1. How does the pH scale work?
2. Why do atoms form covalent bonds?
3. What is the difference between ionic and covalent bonding?

## Architecture
See ARCHITECTURE.md

## Design decisions
- In-memory store + BackgroundTasks for simplicity
- Strong mock fallback for reliability
- Retry + timeout configurable via .env
```

---

## 14. Nội dung bắt buộc ARCHITECTURE.md

```markdown
# Architecture

## Overview
...

## Boundaries
API | Domain/Pipeline | Store | External (LLM/TTS/Media)

## Job Lifecycle
PENDING → RUNNING → COMPLETED / FAILED

## Pipeline steps
1. Knowledge load
2. Script generation (LLM + retry + mock)
3. Quality gate
4. Visual generation
5. TTS
6. Assemble

## Fallback strategy
Every non-deterministic step has mock path. Demo never hard-fails on provider error.

## Trade-offs
...
```

---

## 15. Timeline session (phút-by-phút)

| Phút   | Việc                                      | Có thể cắt nếu trễ      |
|--------|-------------------------------------------|-------------------------|
| 0–8    | Đọc brief + chốt architecture + boundaries | —                       |
| 8–12   | Nói plan (recording)                      | —                       |
| 12–25  | Scaffold + models + store + API routes    | —                       |
| 25–40  | LLM client + script_gen + quality gate    | —                       |
| 40–55  | Visual gen (Pillow + 1 chart)             | Giảm số slide           |
| 55–70  | TTS + assembler                           | Chỉ audio + images, bỏ video |
| 70–90  | End-to-end 3 query + fix bugs             | —                       |
| 90–105 | README + ARCHITECTURE + demo.sh           | Rút gọn README          |
| 105–120| Final test + commit                       | —                       |

**Đoạn plan trên recording:** phút 8–12.

---

## 16. Commit / share / deliverables

- Commit message: `feat: chemistry learner prototype - async job + multimodal pipeline`
- Repo private (nếu brief yêu cầu)
- Đảm bảo `outputs/` có `.gitkeep`, không commit artifact lớn
- Có thể zip `outputs/` của 3 job thành công để đính kèm

---

## 17. Lỗi thường gặp cần tránh

- Quên `BackgroundTasks` → job không chạy
- Update store không thread-safe
- LLM trả text thay vì JSON → validate fail liên tục
- Path artifacts hard-code sai
- ffmpeg không có trong PATH
- edge-tts cần internet (có fallback silent audio nếu cần)
- Scope creep: thêm query mới / UI / auth

---

## 18. Đoạn nói plan mẫu (30–60 giây)

“Em sẽ làm một FastAPI service với job lifecycle sạch: POST tạo job trả id ngay, background task chạy pipeline. Pipeline gồm 6 bước: load knowledge → generate script bằng Gemini có retry và mock fallback → quality gate → tạo slide bằng Pillow và chart matplotlib → TTS bằng edge-tts → ghép bằng ffmpeg. Ưu tiên reliability và 3 query bắt buộc chạy end-to-end. Visual giữ đơn giản đủ giáo dục. In-memory store, không DB. Timebox 90–120 phút, em sẽ cắt video assemble nếu trễ để đảm bảo demo ổn định.”

---

**END OF PLAYBOOK**
```

