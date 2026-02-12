"""
Phase 5 CI gate: validate Render blueprint canary configuration.

We intentionally avoid non-stdlib YAML parsers in CI.
This script performs a minimal, robust-enough scan of render.yaml to ensure:
- main services keep ENABLE_REALTIME_INGESTION disabled
- canary services have ENABLE_REALTIME_INGESTION enabled
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[2]
RENDER_YAML = ROOT / "render.yaml"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_service_blocks(text: str) -> Dict[str, str]:
    """
    Split render.yaml into service blocks keyed by service name.
    Assumes Render blueprint structure:
      services:
        - type: ...
          name: ...
    """
    # Normalize newlines for consistent scanning.
    text = text.replace("\r\n", "\n")

    # Find all service start positions (two-space indent list items).
    starts = [m.start() for m in re.finditer(r"(?m)^\s{2}-\s+type:\s+", text)]
    if not starts:
        return {}

    blocks: Dict[str, str] = {}
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        block = text[start:end]
        name_match = re.search(r"(?m)^\s{4}name:\s+([^\n]+)\s*$", block)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        blocks[name] = block
    return blocks


def _find_env_value(block: str, key: str) -> Optional[str]:
    """
    Find `value: "..."` for a given env var key inside a service block.
    Returns the unquoted value string, or None if not found.
    """
    block = block.replace("\r\n", "\n")
    # Find the `- key: KEY` line, then capture the next `value: ...` within a small window.
    # This keeps us resilient to envVars ordering while avoiding full YAML parsing.
    m = re.search(
        rf"(?ms)^\s{{6}}-\s+key:\s+{re.escape(key)}\s*$.*?^\s{{8}}value:\s+\"([^\"]*)\"\s*$",
        block,
    )
    if not m:
        return None
    return m.group(1)


def main() -> int:
    if not RENDER_YAML.exists():
        print(f"[phase5_render_gate] render.yaml not found at {RENDER_YAML}")
        return 1

    text = _read_text(RENDER_YAML)
    blocks = _split_service_blocks(text)
    if not blocks:
        print("[phase5_render_gate] Failed to detect any services in render.yaml")
        return 1

    expectations = {
        "verified-digital-twin-backend": "false",
        "verified-digital-twin-worker": "false",
        "verified-digital-twin-backend-canary": "true",
        "verified-digital-twin-worker-canary": "true",
    }

    ok = True
    for name, expected in expectations.items():
        block = blocks.get(name)
        if not block:
            print(f"[phase5_render_gate] Missing service block: {name}")
            ok = False
            continue
        actual = _find_env_value(block, "ENABLE_REALTIME_INGESTION")
        if actual is None:
            print(f"[phase5_render_gate] {name}: missing ENABLE_REALTIME_INGESTION env var")
            ok = False
            continue
        if actual != expected:
            print(
                f"[phase5_render_gate] {name}: ENABLE_REALTIME_INGESTION expected={expected} actual={actual}"
            )
            ok = False

    if not ok:
        return 1

    print("[phase5_render_gate] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

