# persona-test

Run the end-to-end persona test suite against production.

## What this does
1. Creates Supabase test accounts for each persona
2. Creates profiles and kicks off deep research
3. Polls until research completes
4. Compiles research into the twin knowledge base
5. Tests chat quality with 5 persona-specific questions per figure
6. Scores each response (in-character, substance, conversational quality)
7. Prints a final quality report with grades

## Usage

```
# Test all 5 default personas (Elon Musk, Arnold, Buffett, Trump, Modi)
python scripts/persona_e2e_test.py

# Test a single persona
python scripts/persona_e2e_test.py --name "Elon Musk"

# Test any public figure by name
python scripts/persona_e2e_test.py --name "Steve Jobs"

# Skip research (test chat only, using existing accounts)
python scripts/persona_e2e_test.py --chat-only

# Run sequentially instead of parallel
python scripts/persona_e2e_test.py --sequential
```

## When to run
- After any change to the chat pipeline, agent, or system prompt
- After model upgrades
- Before a production release
- When investigating persona quality issues

## Interpreting results
- Score 80+/100 = A grade, production ready
- Score 65-79 = B grade, acceptable
- Score 50-64 = C grade, needs investigation
- Score below 50 = F, broken — check auth_guard, twin status, retrieval pipeline

## What to do if a persona fails

Run the full analysis task using:
```
Review the output of `python scripts/persona_e2e_test.py --name "{persona_name}"` and:
1. Check if the twin status is `persona_built` (not `draft`) in Supabase twins table
2. Verify Pinecone has chunks for the twin namespace
3. Check the system prompt is rendering correctly
4. Confirm the deployment includes the Deep Research runtime env vars it still uses (for example `NAME_ONLY_DEEP_RESEARCH_ENABLED`, `SEARCH_PROVIDER`, and model/provider keys)
```

$ARGUMENTS
