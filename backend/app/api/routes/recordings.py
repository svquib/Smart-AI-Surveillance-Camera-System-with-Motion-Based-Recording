"""Recordings = the actual clip files on disk.

Events live in the DB; the video files live in storage/recordings. This router
lists what's on disk (reading the .json sidecars the recorder writes) and lets
you stream a clip back. Once Phase 8 stores events properly we mostly serve
clips by event, but listing the folder is handy for debugging.
"""

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.core.config import settings
from app.models.user import User

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("")
def list_recordings(_: User = Depends(get_current_user)):
    rec_dir: Path = settings.RECORDINGS_DIR
    items = []
    for video in sorted(rec_dir.glob("*.mp4"), reverse=True):
        meta = {}
        sidecar = video.with_suffix(".json")
        if sidecar.exists():
            try:
                meta = json.loads(sidecar.read_text())
            except json.JSONDecodeError:
                pass  # corrupt sidecar - skip metadata, still list the file
        items.append({"filename": video.name, "metadata": meta})
    return {"count": len(items), "recordings": items}


@router.get("/{filename}")
def get_recording(filename: str, _: User = Depends(get_current_user)):
    # Block path traversal - only allow a bare filename inside the folder.
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = settings.RECORDINGS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(path, media_type="video/mp4", filename=filename)
