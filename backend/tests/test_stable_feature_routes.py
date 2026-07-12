import asyncio
import importlib
import os
import sys
from contextlib import contextmanager


@contextmanager
def _import_main_with_env(**overrides):
    saved_env = {key: os.environ.get(key) for key in overrides}
    original_main = sys.modules.pop("main", None)

    try:
        for key, value in overrides.items():
            os.environ[key] = value
        importlib.invalidate_caches()
        yield importlib.import_module("main")
    finally:
        sys.modules.pop("main", None)
        if original_main is not None:
            sys.modules["main"] = original_main
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _get_route(app, path: str, method: str):
    for route in app.routes:
        route_path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        if route_path == path and method.upper() in methods:
            return route
    return None


def test_stable_routes_ignore_legacy_disable_flags():
    with _import_main_with_env(
        ENABLE_REALTIME_INGESTION="false",
        ENABLE_ADVISOR_RETRIEVAL="false",
    ) as main:
        advisor_health = _get_route(main.app, "/retrieval/health", "GET")
        assert advisor_health is not None

        realtime_health = _get_route(main.app, "/ingestion/realtime/health", "GET")
        assert realtime_health is not None
        health_payload = asyncio.run(realtime_health.endpoint())
        assert health_payload["enabled"] is True

        realtime_config = _get_route(main.app, "/ingestion/realtime/config", "GET")
        assert realtime_config is not None
        config_payload = asyncio.run(realtime_config.endpoint())
        assert config_payload["enabled"] is True
