"""
Runs before any test module is collected/imported. Rate limiting is disabled for the
whole test suite here (not per-file) because app.rate_limit.limiter is a module-level
singleton decided at import time — by the time an individual test file's own
os.environ assignments run, whichever test file pytest imports first has often already
triggered `from app.main import app`, which imports app.rate_limit. Setting this here,
in conftest.py, guarantees it happens first.
"""
import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
