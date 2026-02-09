"""
Prompt evolution utility.

Mode A (legacy): pattern-based prompt improvement suggestions.
Mode B (Phase 5): persona prompt optimization (APO-style variant search).

Usage examples:
  python .agent/tools/evolve_prompts.py
  python .agent/tools/evolve_prompts.py --mode pattern
  python .agent/tools/evolve_prompts.py --mode persona --twin-id <uuid> --persist --apply-best
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


# Paths
AGENT_DIR = Path(__file__).parent.parent
LEARNINGS_DIR = AGENT_DIR / "learnings"
PATTERNS_FILE = LEARNINGS_DIR / "pattern_analysis.json"
EVOLUTION_LOG = AGENT_DIR.parent / "docs" / "ai" / "improvements" / "prompt_evolution_log.md"

REPO_ROOT = AGENT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def evolve_prompts_based_on_learnings() -> Dict[str, Any]:
    """
    Legacy pattern-analysis recommendations.
    """
    if not PATTERNS_FILE.exists():
        result = {
            "error": "No pattern analysis available",
            "message": f"Run analyze_workflows.py first. No file at {PATTERNS_FILE}",
        }
        print(f"[EVOLUTION] {result['message']}")
        return result

    try:
        analysis = json.loads(PATTERNS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in pattern analysis: {e}"}

    recommendations = analysis.get("recommendations", [])
    if not recommendations:
        return {
            "message": "No recommendations to process",
            "changes_proposed": 0,
            "changes": [],
        }

    important_recs = [r for r in recommendations if r.get("priority") in ["high", "medium"]]
    changes = []
    for rec in important_recs:
        change = {
            "date": datetime.now().isoformat(),
            "reason": rec.get("issue", "Unknown issue"),
            "suggestion": rec.get("suggestion", ""),
            "action": rec.get("action", ""),
            "prompt_file": determine_prompt_file(rec),
            "location": determine_location(rec),
            "priority": rec.get("priority", "medium"),
            "recommendation_type": rec.get("type", "unknown"),
        }
        changes.append(change)

    if changes:
        log_evolution(changes)

    result = {
        "mode": "pattern",
        "changes_proposed": len(changes),
        "changes": changes,
        "message": f"Generated {len(changes)} prompt improvement suggestions",
    }
    print(f"[EVOLUTION] {result['message']}")
    if changes:
        print(f"[EVOLUTION] Changes logged to {EVOLUTION_LOG}")
    return result


def determine_prompt_file(recommendation: Dict[str, Any]) -> str:
    rec_type = recommendation.get("type", "")
    issue = recommendation.get("issue", "").lower()
    if "error_pattern" in rec_type or "error" in issue:
        return "AGENTS.md"
    if "workflow" in issue or "command" in issue:
        return "docs/ai/commands/"
    if "auth" in issue:
        return "docs/ops/AUTH_TROUBLESHOOTING.md"
    if "database" in issue or "schema" in issue:
        return "docs/KNOWN_FAILURES.md"
    return "AGENTS.md"


def determine_location(recommendation: Dict[str, Any]) -> str:
    rec_type = recommendation.get("type", "")
    action = recommendation.get("action", "").lower()
    if "common ai failure patterns" in action:
        return "Common AI Failure Patterns section"
    if "command card" in action:
        return "Relevant command card"
    if "workflow" in action:
        return "Relevant workflow file"
    if "error_pattern" in rec_type:
        return "Common AI Failure Patterns section"
    return "Appropriate section based on context"


def log_evolution(changes: List[Dict[str, Any]]) -> None:
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    if EVOLUTION_LOG.exists():
        content = EVOLUTION_LOG.read_text(encoding="utf-8")
    else:
        content = "# Prompt Evolution Log\n\n"
        content += "Tracks how prompts evolve from workflow outcomes and optimization loops.\n\n---\n"

    date_str = datetime.now().strftime("%Y-%m-%d")
    section = f"\n## {date_str}\n\n"
    for change in changes:
        priority = str(change.get("priority", "medium")).upper()
        section += f"### [{priority}] {change['reason']}\n\n"
        section += f"**Suggestion:** {change['suggestion']}\n\n"
        section += f"**Location:** `{change['prompt_file']}` -> {change['location']}\n\n"
        section += f"**Action:** {change.get('action', 'Review and implement manually')}\n\n"
        section += "---\n\n"

    EVOLUTION_LOG.write_text(content + section, encoding="utf-8")


async def run_persona_optimization(args: argparse.Namespace) -> Dict[str, Any]:
    from eval.persona_prompt_optimizer import optimize_persona_prompts

    summary = await optimize_persona_prompts(
        twin_id=args.twin_id,
        tenant_id=args.tenant_id,
        created_by=args.created_by,
        dataset_path=args.dataset,
        spec_path=args.spec_path,
        candidates=None,
        generator_mode=args.generator_mode,
        model=args.model,
        apply_best=args.apply_best,
        persist=args.persist,
    )
    return {"mode": "persona", **summary}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prompt evolution utility")
    parser.add_argument(
        "--mode",
        choices=["pattern", "persona"],
        default="pattern",
        help="Evolution mode: pattern (legacy) or persona (Phase 5 optimizer)",
    )
    parser.add_argument("--twin-id", type=str, default=None, help="Twin ID for persona mode")
    parser.add_argument("--tenant-id", type=str, default=None, help="Tenant ID for persistence")
    parser.add_argument("--created-by", type=str, default=None, help="Owner user ID for persistence")
    parser.add_argument("--dataset", type=str, default=None, help="Dataset path for persona mode")
    parser.add_argument("--spec-path", type=str, default=None, help="Persona spec JSON path")
    parser.add_argument(
        "--generator-mode",
        type=str,
        default="auto",
        choices=["auto", "heuristic", "openai"],
        help="Generation mode for persona optimization",
    )
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="Model for openai generator mode")
    parser.add_argument("--apply-best", action="store_true", help="Activate best variant in persistence mode")
    parser.add_argument("--persist", action="store_true", help="Persist optimization run artifacts")
    parser.add_argument("--output", type=str, default=None, help="Optional path to write output JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "pattern":
        result = evolve_prompts_based_on_learnings()
    else:
        result = asyncio.run(run_persona_optimization(args))

    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")

    if result.get("error") or result.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
