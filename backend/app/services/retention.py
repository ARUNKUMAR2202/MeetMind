"""
FERPA/GDPR data-minimization item from the thesis (Chapter 4, Layer 7): audio
shouldn't be kept forever after a session is fully processed. This runs a periodic
sweep that deletes the stored local audio file for any session that:
  - is "completed" (processing succeeded — nothing to gain from keeping the audio
    for a failed session either, but leaving those alone in case someone wants to
    retry rather than re-upload)
  - completed more than AUDIO_RETENTION_DAYS ago
  - still has an audio_path (hasn't already been purged)

The TRANSCRIPT and all pipeline outputs (summaries, quiz, action items) are kept —
only the raw audio is deleted, since that's the sensitive recording; the derived
text outputs are the actual product.

Set AUDIO_RETENTION_DAYS=0 to disable (keep audio indefinitely).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from ..config import settings
from ..database import SessionLocal
from ..models import MeetingSession
from .storage_service import delete_audio

_CHECK_INTERVAL_SECONDS = 3600  # hourly is plenty for a day-granularity retention window


def run_retention_sweep_once() -> int:
    """Synchronous — safe to call directly from a script or a test. Returns count purged."""
    if settings.audio_retention_days <= 0:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audio_retention_days)
    db = SessionLocal()
    purged = 0
    try:
        candidates = (
            db.query(MeetingSession)
            .filter(MeetingSession.status == "completed")
            .filter(MeetingSession.completed_at.isnot(None))
            .filter(MeetingSession.completed_at < cutoff)
            .filter(MeetingSession.audio_path != "")
            .all()
        )
        for session in candidates:
            delete_audio(session.audio_path)
            session.audio_path = ""
            purged += 1
        if purged:
            db.commit()
    finally:
        db.close()
    return purged


async def _loop() -> None:
    while True:
        try:
            run_retention_sweep_once()
        except Exception:
            pass  # a retention hiccup should never take down the periodic loop
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)


def start_retention_job() -> asyncio.Task | None:
    """Called once from main.py's lifespan. Returns None (and starts nothing) if
    retention is disabled, so there's no dangling task to worry about."""
    if settings.audio_retention_days <= 0:
        return None
    return asyncio.create_task(_loop())
