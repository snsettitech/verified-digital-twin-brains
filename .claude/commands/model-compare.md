# model-compare

Compare GPT-4.1 vs Gemini 2.5 Flash for persona chat quality using the production system prompt.

## What this does
1. Takes a persona (or all 5 default personas)
2. Runs identical questions through GPT-4.1 and Gemini 2.5 Flash simultaneously
3. Scores both on: in-character adherence, substance, conversational quality, directness
4. Reports winner, quality gap %, and latency
5. Gives a final recommendation

## Usage

```
# Compare all personas
python scripts/model_quality_compare.py

# Compare a specific persona
python scripts/model_quality_compare.py --persona "Elon Musk"

# More questions per persona
python scripts/model_quality_compare.py --persona "Warren Buffett" --questions 5
```

## Required env vars
- `OPENAI_API_KEY` — in backend/.env
- `GOOGLE_API_KEY` — in backend/.env

## When to run
- When evaluating whether to switch primary inference provider
- After model version upgrades (e.g., gpt-4o → gpt-4.1)
- When users report low-quality persona responses
- To set INFERENCE_PROVIDER in render.yaml based on real data

## Current config (render.yaml)
- Primary: `openai` / `gpt-4.1`
- Fallback: `gemini-2.5-flash`
- To switch primary to Gemini: set `INFERENCE_PROVIDER=gemini` in render.yaml

$ARGUMENTS
