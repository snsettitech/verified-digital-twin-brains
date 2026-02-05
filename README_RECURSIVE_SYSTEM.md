# Recursive Prompting System - Quick Start

This document provides a quick overview of the recursive prompting system. For full documentation, see `docs/ai/recursive_system.md`.

## What Is This?

A system that captures workflow outcomes, analyzes patterns, and suggests prompt improvements to make AI agents more effective over time.

## Quick Usage

### 1. Capture a Workflow Outcome

After completing any workflow:

```python
from .agent.tools.capture_outcome import capture_outcome
import time

start = time.time()
# ... do your work ...
duration = time.time() - start

capture_outcome(
    workflow_type="feature_development",
    success=True,
    duration_seconds=duration,
    errors=[],  # List any errors
    improvements_needed=[],  # What would help?
    metadata={"feature": "my_feature"}
)
```

### 2. Analyze Patterns (Weekly/Monthly)

```bash
python .agent/tools/analyze_workflows.py
```

Generates:
- `.agent/learnings/pattern_analysis.json` - Analysis data
- `.agent/learnings/improvement_suggestions.md` - Suggestions

### 3. Generate Prompt Improvements

```bash
python .agent/tools/evolve_prompts.py
```

Generates:
- `docs/ai/improvements/prompt_evolution_log.md` - Suggested changes

### 4. Apply Improvements

Review the evolution log and manually update:
- `AGENTS.md`
- Command cards (`docs/ai/commands/`)
- Workflows (`.agent/workflows/`)
- Troubleshooting docs (`docs/ops/`)

## File Structure

```
.agent/
├── tools/
│   ├── capture_outcome.py      # Log outcomes
│   ├── analyze_workflows.py    # Analyze patterns
│   └── evolve_prompts.py       # Generate suggestions
└── learnings/
    ├── workflow_outcomes.json  # Raw data
    ├── pattern_analysis.json   # Analysis results
    └── improvement_suggestions.md  # Suggestions

docs/ai/
├── recursive_system.md          # Full documentation
└── improvements/
    └── prompt_evolution_log.md  # Change log
```

## Integration

- **Workflows**: Use `.agent/workflows/with-feedback.md` template
- **PRs**: Include "improvements needed" in PR descriptions
- **CI**: Can capture outcomes automatically (future enhancement)

## Benefits

- **Compounds knowledge** - System gets smarter over time
- **Identifies patterns** - Common issues become visible
- **Improves prompts** - Instructions get better
- **Tracks metrics** - Success rates and durations measured

For full documentation, see `docs/ai/recursive_system.md`.
