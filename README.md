# Smart AI Surveillance Camera System

Motion-based recording, object classification, suspicious-activity detection, and emergency SOS alerts — built as a real-world, production-style system.

This project is built **phase by phase**. You are currently at **Phase 1 — Project setup & environment**.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, FastAPI, Uvicorn |
| Data | SQLAlchemy + SQLite (dev) / PostgreSQL (prod) |
| Computer vision | OpenCV, YOLOv11 (Ultralytics), MediaPipe Pose, PyTorch |
| Frontend | React, Tailwind CSS, Axios, WebSocket |
| Storage | Local filesystem (S3 as a future option) |
| Notifications | Telegram Bot API (email optional) |
| Auth | JWT |
| Deployment | Docker |

## Roadmap

1. **Project setup & environment** ← _you are here_
2. Camera connection (OpenCV)
3. Motion detection
4. Motion-based recording
5. YOLOv11 object detection
6. Activity recognition (MediaPipe Pose)
7. FastAPI backend (auth, cameras, events, alerts)
8. Database integration
9. React dashboard
10. SOS alerts (Telegram)
11. Docker deployment

## Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app factory + entrypoint
│   │   ├── core/              # config, logging, security
│   │   ├── api/               # routers (health now; auth/events/... later)
│   │   │   ├── router.py
│   │   │   └── routes/
│   │   ├── db/                # SQLAlchemy engine/session (Phase 8)
│   │   ├── models/            # ORM models (Phase 8)
│   │   ├── schemas/           # Pydantic request/response models
│   │   ├── services/          # business logic (recording, alerts, ...)
│   │   ├── vision/            # OpenCV / YOLO / MediaPipe pipelines (Phase 2-6)
│   │   └── utils/             # helpers
│   ├── tests/                 # pytest suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/                  # React app (Phase 9)
├── storage/
│   ├── recordings/            # saved video clips
│   └── snapshots/             # saved alert snapshots
├── .gitignore
└── README.md
```

### Why this layout (clean architecture)

The code is split by **responsibility**, not by phase, so each layer can change independently:

- `api/` only handles HTTP concerns (routing, request/response).
- `services/` holds business logic and is callable from API routes, the camera worker, or tests.
- `vision/` isolates all OpenCV/ML code so the rest of the app never imports heavy CV libraries directly.
- `models/` + `db/` own persistence.
- `core/config.py` is the single source of truth for settings, loaded from environment variables.

This separation is what keeps the project maintainable as it grows to 11 phases.

## Setup (Phase 1)

Requires **Python 3.11+**.

```bash
cd backend

# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate

# 2. Install Phase 1 dependencies
pip install -r requirements.txt

# 3. Create your local env file
cp .env.example .env                 # Windows: copy .env.example .env
```

> The computer-vision packages (OpenCV, Ultralytics/YOLOv11, MediaPipe, Torch)
> are intentionally **commented out** in `requirements.txt`. They are large and
> only needed from Phase 2 onward. Install them when you reach those phases.

## Run

```bash
# from backend/, with the venv active
uvicorn app.main:app --reload
```

Then open:

- API root: http://localhost:8000/
- Interactive docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/api/v1/health

A healthy response looks like:

```json
{ "status": "ok", "app": "Smart AI Surveillance System", "version": "0.1.0", ... }
```

## Test

```bash
# from backend/, with the venv active
pytest -q
```

Both smoke tests (`/` and `/api/v1/health`) should pass.

## Possible improvements

- Add `ruff` + `black` + `pre-commit` for linting/formatting.
- Add a `pyproject.toml` to formalise the package and pin Python version.
- Split `requirements.txt` into `base` / `vision` / `dev` files.
- Add structured (JSON) logging once running under Docker.
