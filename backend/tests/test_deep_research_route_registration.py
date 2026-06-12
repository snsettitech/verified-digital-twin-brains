import os
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_deep_research_routes_register_when_legacy_env_false():
    env = os.environ.copy()
    env.update(
        {
            "SUPABASE_URL": "test",
            "OPENAI_API_KEY": "test",
            "PINECONE_API_KEY": "test",
            "PINECONE_INDEX_NAME": "test",
            "SUPABASE_SERVICE_KEY": "test",
            "JWT_SECRET": "test",
            "DEV_MODE": "false",
            "DEEP_RESEARCH_ENABLED": "false",
            "NAME_ONLY_DEEP_RESEARCH_ENABLED": "true",
        }
    )

    script = """
import main

paths = {route.path for route in main.app.router.routes}
required = {
    "/deep-research/runs",
    "/twins/{twin_id}/crawls",
    "/twins/{twin_id}/research/{research_run_id}/continue-claims",
}
missing = sorted(required - paths)
assert not missing, f"missing routes: {missing}"
print("deep research routes mounted")
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
