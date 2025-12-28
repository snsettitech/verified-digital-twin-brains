# backend/tests/conftest.py
"""Pytest configuration for backend tests.

Adds the backend directory to Python path so tests can import modules.
Registers custom pytest markers.
"""

import sys
import os
import pytest

# Add backend directory to path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access (skipped in CI)"
    )
