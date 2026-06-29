# Smart AI Surveillance Camera System

A surveillance system that doesn't waste resources recording an empty room. It
watches a camera feed, only records when something actually moves, figures out
*what* moved (person, animal, vehicle) and *what they're doing* (walking,
running, falling), flags anything suspicious, and exposes the whole thing
through a REST API.

I'm building this in phases rather than dumping everything at once, so each
piece can be tested on its own before the next one goes on top.

## Where it's at

- [x] **Phase 1** – Project setup, config, FastAPI skeleton
- [x] **Phase 2** – Camera connection (webcam + RTSP) with OpenCV
- [x] **Phase 3** – Motion detection (background subtraction / frame diff)
- [x] **Phase 4** – Motion-based recording with pre-roll + cooldown
- [x] **Phase 5** – Object detection with YOLOv11
- [x] **Phase 6** – Activity recognition with MediaPipe Pose
- [x] **Phase 7** – FastAPI backend: JWT auth + cameras/events/alerts/recordings
- [ ] **Phase 8** – Database integration (Alembic, pipeline writes events)
- [ ] **Phase 9** – React dashboard
- [ ] **Phase 10** – SOS alerts (Telegram)
- [ ] **Phase 11** – Docker

## Stack

Python + FastAPI + SQLAlchemy on the backend (SQLite for dev, Postgres for
prod). OpenCV / YOLOv11 / MediaPipe for the vision side. JWT for auth. React +
Tailwind for the dashboard (later). Telegram for alerts (later).

## How the vision pipeline fits together

The whole point is to do expensive work only when it's worth it:

```
Camera frame
   │
   ▼
Motion?  ──no──►  do nothing (cheap, runs all day)
   │yes
   ▼
YOLOv11  →  what's in frame (person/cat/dog/vehicle/…)
   │
   ▼
MediaPipe Pose  →  what they're doing (standing/walking/running/falling)
   │
   ▼
Record clip (with the few seconds *before* motion) + log the event
```

Each stage is its own module under `backend/app/vision/`, so the motion
detector has no idea YOLO exists, YOLO has no idea pose estimation exists, etc.
That separation is what's kept things sane across seven phases.

## Project layout

```
backend/
  app/
    main.py            FastAPI app + startup
    core/              config, logging, security (JWT/passwords)
    api/
      router.py        pulls all routers together
      deps.py          get_current_user, etc.
      routes/          health, auth, cameras, events, alerts, recordings
    db/                engine, session, Base
    models/            User, Camera, Event, Alert (SQLAlchemy)
    schemas/           Pydantic request/response models
    services/          recorder.py (more business logic lands here)
    vision/            camera, motion, detector, pose, activity
  scripts/             standalone test tools for each vision phase
  tests/
  requirements.txt
  .env.example
storage/
  recordings/          saved clips + .json sidecars
  snapshots/           trigger-moment stills
frontend/              React app (Phase 9)
```

## Getting it running

You need Python 3.11+. On macOS the command is `python3`.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # then edit SECRET_KEY at least
```

> Heads up: `requirements.txt` pulls in PyTorch (via ultralytics) and
> mediapipe, so the first install is a big download. numpy is pinned to 1.26.x
> on purpose — ultralytics doesn't support numpy 2.x yet.

Start the API:

```bash
uvicorn app.main:app --reload
```

- Swagger UI:  http://localhost:8000/docs
- Health:      http://localhost:8000/api/v1/health

### Trying the API

Everything except `/health` needs a token. Quickest path through Swagger:

1. `POST /api/v1/auth/register` with a name/email/password.
2. Click **Authorize** (top right), enter the same email/password — Swagger
   grabs a token and attaches it to every request after that.
3. Now `POST /api/v1/cameras` to add a camera, `GET /api/v1/events`, etc.

Or from the terminal:

```bash
# register
curl -X POST localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Admin","email":"admin@test.com","password":"secret123"}'

# login -> grab the access_token
curl -X POST localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"secret123"}'

# use it
curl localhost:8000/api/v1/cameras -H "Authorization: Bearer <token>"
```

## Testing the vision side (no API needed)

Each phase has a standalone script under `backend/scripts/` so you can eyeball
it working. Run them from `backend/` with the venv active:

```bash
python scripts/preview_camera.py        # Phase 2 - raw feed
python scripts/preview_motion.py        # Phase 3 - motion boxes
python scripts/record_on_motion.py      # Phase 4 - records clips on motion
python scripts/preview_detection.py     # Phase 5 - YOLO labels  (--device mps on Apple)
python scripts/detect_on_motion.py      # Phase 5 - YOLO only when motion
python scripts/preview_activity.py       # Phase 6 - pose skeleton + activity
```

macOS will ask for camera permission the first time — allow it for your
terminal under System Settings → Privacy & Security → Camera.

## Running tests

```bash
pytest -q
```

## Notes / things I'd still improve

- Motion + detection currently run in the request/script thread. Moving capture
  to its own thread would stop a slow consumer from dropping frames.
- Fall detection is rule-based and needs calibrating to your camera angle —
  treat it as "flag it for a human", not gospel.
- Tokens don't refresh yet; for a real deployment I'd add refresh tokens and
  proper user roles.
