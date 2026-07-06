"""
Local-disk audio storage. `save_audio` returns a path string, `get_local_path`
resolves it back to a real file for the pipeline to read — kept as separate
functions (rather than just using the path directly) so a future remote storage
backend (Supabase Storage, once Phase 3 wires it in) can slot in behind the same
interface without touching callers.
"""
import os

from ..config import settings


def _local_dir() -> str:
    os.makedirs(settings.upload_dir, exist_ok=True)
    return settings.upload_dir


def save_audio(file_bytes: bytes, original_filename: str, session_id: str) -> str:
    ext = os.path.splitext(original_filename)[1] or ".webm"
    local_path = os.path.join(_local_dir(), f"{session_id}{ext}")
    with open(local_path, "wb") as f:
        f.write(file_bytes)
    return local_path


def get_local_path(stored_path: str) -> str:
    return stored_path


def delete_audio(stored_path: str) -> None:
    """Best-effort delete — called when a session is removed. Never raises."""
    try:
        if stored_path and os.path.exists(stored_path):
            os.remove(stored_path)
    except Exception:
        pass
