# e2e-smoke

Quick smoke test — verifies the production API is alive and a single persona can chat.
Takes ~5 minutes (uses existing test account, skips research).

## What this does
1. Authenticates as `qa.elon.musk@personaon-test.io`
2. Gets existing twin (assumes research already compiled)
3. Sends 2 quick chat questions
4. Reports pass/fail with scores

## Usage

```
python scripts/persona_e2e_test.py --name "Elon Musk" --chat-only
```

## When to run
- After every deploy to verify production is working
- When a user reports chat is broken
- As a quick "is the site up and responding?" check

## Expected output (healthy system)
```
[6/6] Testing chat (5 questions)...
  Q1: What's your vision for humanity becoming multi-planetary?
  A:  The reason I started SpaceX wasn't to make money...
      Score: 82/100 | in_char=9 sub=8 no_ai=10 conv=9
...
  Average quality score: 78/100
  Grade: B
```

## If it fails
Check in order:
1. Is Render service running? Check https://dashboard.render.com
2. If the name-only JSON flow is failing, is `NAME_ONLY_DEEP_RESEARCH_ENABLED=true` in Render env vars? (Core deep-research routes are always registered.)
3. Is the twin status `persona_built`? (Check Supabase twins table)
4. Are there Pinecone vectors for this twin? (Check retrieval pipeline)

$ARGUMENTS
