# MeetMind AI

Turns lecture and meeting audio into structured, role-specific intelligence —
topic summaries + quizzes for students, action items + role summaries for teams —
the moment a session ends. Supports uploading a recording OR starting a **live
video-conference meeting** directly in the app. See `TASK_SPLIT.md` for how the
remaining work is divided across the team, including exactly what's been genuinely
tested vs. what's written-but-unverified.

## Project layout

```
ai-pipeline/   Python package: transcription, diarization, summarization, modular
               quiz generation (Q&A -> distractors -> quality filter, batched into
               2 LLM calls per section), action items, RAG. Evaluation scripts in
               scripts/. No web framework dependency.
backend/       FastAPI app. Auth (JWT + httpOnly cookies), rate limiting, session
               upload/live/delete/download, WebRTC signaling, Redis-backed pub/sub
               (falls back to in-memory), audio auto-deletion job, background
               pipeline execution.
frontend/      Next.js 14 (App Router) + TypeScript + Tailwind. Upload flow, live
               video-conference room, dashboards with an audio player + transcript
               view + click-to-seek, step-by-step processing indicator.
```

Every layer runs end-to-end in **mock mode** — no API keys required. **55 tests**
pass across both Python packages (30 backend, 25 AI pipeline), several run against
**real Redis and real Postgres** during development (not just mocked — see
`TASK_SPLIT.md`'s "what got genuinely verified" section), plus a clean `npm run build`.

## Quickstart — option A: Docker Compose

```bash
cp backend/.env.example backend/.env   # fill in your real API keys, or leave
                                        # USE_MOCK_PIPELINE=true to try it first
docker compose up --build
```

Frontend: http://localhost:3000 · Backend: http://localhost:8000/docs

Starts Postgres, Redis, the backend, and the frontend together — Redis backs both
session-status updates and video-room signaling (see `TASK_SPLIT.md`).

> No Docker daemon was available in the environment this was built in, so the
> Compose file and Dockerfiles are carefully hand-verified (YAML validated, build
> steps traced through) but not build-tested end-to-end. Postgres and Redis
> themselves ARE genuinely tested — just by installing and running them directly,
> not through Compose specifically. Expect normal first-run rough edges.

## Quickstart — option B: run each piece directly

**Backend:**
```bash
cd backend
python -m venv venv && .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # defaults to USE_MOCK_PIPELINE=true, SQLite, in-memory pub/sub
uvicorn app.main:app --reload --port 8000
```

**Frontend** (separate terminal):
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000, create an account, and either:
- **Upload a recording** — any audio/video file (mock mode ignores the content
  and returns realistic sample data), or
- **Start a live meeting** — opens a video-conference room (camera/mic permission
  requested), records the mixed audio, copy the invite link for others to join,
  auto-uploads and processes it when you click "End & process."

Once processed, click any quiz question, action item, or transcript line to jump
the audio player to that exact moment.

## Live video conferencing — how it works, and its limits

Mesh WebRTC: every participant connects directly to every other participant via
the backend's signaling relay (`/ws/rooms/{room_id}`). The server only ever relays
small JSON handshake messages; audio/video never touches it. Room membership and
message relay are Redis-backed when `REDIS_URL` is set, so signaling works correctly
even across multiple backend processes (verified with two independent manager
instances talking through real Redis — see `TASK_SPLIT.md`).

- **Good for:** small meetings and study groups, roughly up to 4-6 people.
- **Not built for:** a full lecture hall — mesh connections don't scale past a
  handful of peers. Swap in an SFU (LiveKit, mediasoup) before using this for large
  classes.
- **No TURN server configured** — only public STUN. Calls between peers on
  restrictive/symmetric NATs may fail to connect.
- Only **audio** is recorded and sent to the pipeline; video is for the live call
  only, matching the rest of MeetMind's audio-based architecture.
- **Not yet tested in two real browsers** — the signaling protocol is genuinely
  Redis-tested; the actual peer-to-peer media connection hasn't been tried across
  real machines yet. Do that before a real demo.

## Running against real audio + your own API keys

Put your keys directly in `backend/.env` (don't paste them into a chat or commit
them) — `OPENAI_API_KEY`, `PINECONE_API_KEY` — then set `USE_MOCK_PIPELINE=false`
and restart the backend. Watch the dashboard's step indicator (transcribing →
diarizing → summarizing → ...) instead of a generic spinner while it runs.

### Optional heavier AI backends (real diarization, real BERTScore)

Both off by default, both fall back to a lightweight placeholder otherwise, and
neither has been run against real data in this codebase's own development (no
network access to Hugging Face from this environment) — written and unit-tested
for routing/error-handling only:

- **Real speaker diarization**: `pip install -r ai-pipeline/requirements-real-diarization.txt`,
  get a Hugging Face token, set `USE_REAL_DIARIZATION=true` + `HUGGINGFACE_TOKEN=...`.
- **Real BERTScore**: `pip install -r ai-pipeline/requirements-real-bertscore.txt`,
  set `USE_REAL_BERTSCORE=true`. Needs a reference summary to score against.

### Evaluation scripts (`ai-pipeline/scripts/`)

- `measure_retrieval_latency.py` — implements the thesis's Chapter 5 latency plan
  (50 sessions, target <2s). Has a `--synthetic` self-test mode and a
  `--session-ids-file` real-data mode.
- `calibrate_noise_threshold.py` — helps pick a real value for `config.py`'s
  `noise_threshold` (currently an unvalidated guess) from labeled clean/noisy
  transcript samples.

## Security notes

- Auth uses an httpOnly cookie (set on login/register) as the primary mechanism —
  the frontend no longer stores the raw JWT in localStorage, reducing XSS exposure.
  A bearer token is still returned in the JSON response for API clients/scripts.
- Rate limiting: 5/min on register, 10/min on login, 10/min on session upload
  (`app/rate_limit.py`). Disabled automatically under pytest (see `tests/conftest.py`)
  since the test suite legitimately calls these endpoints far more than any real
  user would in a minute.
- Upload size capped at `MAX_UPLOAD_SIZE_MB` (default 200MB).
- Audio auto-deletes `AUDIO_RETENTION_DAYS` after a session completes (default 30;
  set to 0 to disable) — transcripts and results are kept, only the raw recording
  is purged. FERPA/GDPR data-minimization item from the thesis.

## Tests

```bash
cd ai-pipeline && pip install -r requirements.txt && python -m pytest tests/ -v
cd backend && pip install -r requirements.txt && python -m pytest tests/ -v
```

Both suites run offline by default (mocked OpenAI/Pinecone calls, in-memory
pub/sub). Real-Redis coverage lives entirely in `tests/test_room_manager_redis.py`,
which is self-contained (creates its own Redis connections regardless of any
ambient `REDIS_URL`) and skips gracefully if `redis://localhost:6379/0` isn't
reachable — no setup needed beyond having a Redis server running. Every other test
file explicitly forces in-memory pub/sub for itself, so the rest of the suite's
behavior doesn't change based on your environment's `REDIS_URL`.

## Tech stack

FastAPI + SQLAlchemy (SQLite for local dev, Postgres via Docker Compose — both
genuinely tested), Redis for pub/sub and room signaling, Next.js/React frontend with
WebSocket updates and WebRTC video, OpenAI Whisper + GPT-4o, Pinecone for RAG, AWS S3
for audio storage (falls back to local disk if `AWS_S3_BUCKET` is unset), JWT + httpOnly
cookie auth (swap for Auth0 later — see `backend/app/auth.py`), slowapi for rate
limiting.
