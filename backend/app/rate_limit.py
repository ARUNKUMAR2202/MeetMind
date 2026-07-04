"""
Separate module so both main.py (which registers the exception handler) and any
router (which applies @limiter.limit(...) to individual endpoints) can import the
same Limiter instance without a circular import.

RATE_LIMIT_ENABLED=false (set by the test suite — see tests/conftest.py) turns
limiting off entirely rather than just raising the limits, since slowapi's default
in-memory storage persists counts across the whole test run: dozens of tests each
calling /auth/register would otherwise trip the same per-IP limit a real single
test-client "user" would never realistically hit.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
)
