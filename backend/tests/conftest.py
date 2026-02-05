# backend/tests/conftest.py
"""Pytest configuration for backend tests.

Adds the backend directory to Python path so tests can import modules.
Registers custom pytest markers.
"""

import sys
import os
import pytest
from types import SimpleNamespace

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Ensure feature flags and dev mode are consistent for tests
os.environ.setdefault("ENABLE_ENHANCED_INGESTION", "true")
os.environ.setdefault("DEV_MODE", "false")

# Ensure langfuse decorator doesn't break FastAPI signatures in tests
def _noop_observe(*args, **kwargs):
    def decorator(func):
        return func
    return decorator

sys.modules.setdefault("langfuse", SimpleNamespace(observe=_noop_observe, get_client=lambda: None))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access (skipped in CI)"
    )
