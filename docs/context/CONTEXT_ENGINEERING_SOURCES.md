# Context Engineering Sources

This list captures upstream patterns that informed the workflows and templates in this repo.

## GitHub Repos Reviewed
- `openai/openai-cookbook` — prompt structuring and task scoping.
- `openai/agent-prompts` — role/prompt patterns for deterministic behavior.
- `openai/prompt-engineering` — iterative prompt refinement patterns.
- `openai/agentic-system-prompts` — system prompt structure and layered instruction design.
- `continuedev/continue` — context selection and minimal file loading for IDE agents.
- `aider-ai/aider` — repo mapping and diff-aware context management.
- `nickthecook/repomapper` — automated repo map generation.
- `assafelovic/gpt-researcher` — structured research pipelines and synthesis.
- `sweepai/sweep` — PR-driven change isolation and retrieval of relevant files.
- `promptfoo/promptfoo` — eval harness patterns and prompt regression checks.
- `promptfoo/promptfoo-action` — CI prompt eval automation.
- `dair-ai/awesome-context-engineering` — collection of context engineering patterns.

## Patterns Adopted
- Minimal context pack with deterministic sources.
- Expansion ladder to avoid loading irrelevant files.
- Repo map for quick file discovery.
- Proof-driven development and regression checks.
- Explicit evidence requirements for “unused” claims.
