"""Shareable room codes: short enough to read aloud/type, without characters that
are easy to mix up (0/O, 1/I/L excluded)."""
import secrets

from sqlalchemy.orm import Session as DBSession

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_LENGTH = 6


def generate_room_code(db: DBSession) -> str:
    from ..models import Room

    for _ in range(10):
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
        if db.query(Room).filter(Room.code == code).first() is None:
            return code
    raise RuntimeError("Could not generate a unique room code — this should be practically impossible.")
