# Repository Cleanup Inventory

Generated: 2026-03-10

## Classification Categories

### KEEP (Essential Source/Code)
Files that are required for the application to function.

| Path | Type | Reason |
|------|------|--------|
| `README.md` | Doc | Primary project documentation |
| `CONTRIBUTING.md` | Doc | Contribution guidelines |
| `AGENTS.md` | Doc | Agent-specific guidance |
| `LICENSE` | Doc | License file (if exists) |
| `backend/` | Source | Core application backend |
| `frontend/` | Source | Core application frontend |
| `docs/` (canonical) | Doc | Current operational documentation |
| `scripts/` | Source | Runtime scripts and automation |
| `render.yaml` | Config | Deployment configuration |
| `pytest.ini` | Config | Test configuration |
| `.github/workflows/` | Config | CI/CD configuration |
| `.coderabbit.yaml` | Config | Code review bot config |
| `.cursorrules` | Config | Cursor IDE rules |
| `package/` | Source | Package manifests (if used in deploy) |

### MOVE (Relocate to appropriate area)
Files that should be relocated but kept in repo.

| Path | Destination | Type | Reason |
|------|-------------|------|--------|
| `docs/history/` | docs/archive/ | Archive | Historical docs |
| `docs/ai/improvements/proof_outputs/` | docs/archive/proof_outputs/ | Archive | Verification artifacts |
| Root-level *_IMPLEMENTATION_SUMMARY.md | docs/archive/implementation/ | Archive | Completed work summaries |
| Root-level *_AUDIT*.md (non-current) | docs/archive/audits/ | Archive | Historical audits |
| Root-level *_PLAN.md (completed) | docs/archive/plans/ | Archive | Historical plans |
| Root-level debug/test scripts | tools/manual_verify/ | Tool | Manual verification scripts |
| `proof/` | docs/archive/proof/ | Archive | Proof artifacts |

### REMOVE FROM GIT (Should not be tracked)
Files that should be removed from version control entirely.

| Path | Type | Reason |
|------|------|--------|
| `.model_cache/` | Cache | Downloaded model files |
| `tmp/` | Temp | Temporary files |
| `temp_uploads/` | Temp | Upload staging |
| `artifacts/` | Generated | Generated artifacts, logs |
| `artifacts/*.log` | Log | Dev server logs |
| `proof/*.log` | Log | Debug logs |
| `proof/*.json` | Debug | Debug outputs |
| `proof/*.png` | Screenshot | Screenshots |
| `proof/*.txt` | Log | Console logs |
| `backend/.pytest_cache/` | Cache | Test cache |
| `frontend/playwright-report/` | Generated | Test reports |
| `frontend/playwright-test-results/` | Generated | Test results |
| `frontend/test-results/` | Generated | Test results |
| `frontend/test-results-temp/` | Generated | Temp test results |
| `__pycache__/` | Cache | Python cache |
| `backend/__pycache__/` | Cache | Python cache |
| `*.pyc` | Cache | Python bytecode |
| `live_chat_history.json` | Debug | Debug output |
| `live_conversation_results.json` | Debug | Test output |
| `phase1_2_test_results.json` | Debug | Test output |
| `phase1_evaluation_results.json` | Debug | Test output |
| `phase1_final_results.json` | Debug | Test output |
| `pinecone_results.json` | Debug | Debug output |
| `backend/retrieval_debug_output.json` | Debug | Debug output |
| `backend/eval_debug.log` | Log | Debug log |
| `frontend/devserver.log` | Log | Dev server log |
| `backend/eval/*.json` | Generated | Eval results (keep dir, not files) |
| `deployment_success.png` | Screenshot | One-time artifact |
| `supabase-mcp-server-*.tgz` | Package | Downloaded package |
| `.mcp/` | Generated | Generated MCP configs |
| `.next/` | Generated | Next.js build output |
| `.vercel/` | Generated | Vercel build output |

### ARCHIVE (Move to docs/archive/)
Non-current documentation and reports.

| Path | Category |
|------|----------|
| `5LAYER_*.md` | Implementation |
| `AUDIT_*.md` | Audit |
| `CHUNKING_*.md` | Implementation |
| `CODE_REVIEW_*.md` | Process |
| `CRITICAL_PATH_*.md` | Planning |
| `DEEP_RESEARCH_*.md` | Planning |
| `ADVISOR_*.md` | Planning |
| `DEPLOYMENT_STATUS.md` | Status |
| `DUPLICATION_COMPLEXITY_REPORT.md` | Analysis |
| `FEATURE_FLAGS_EXPLAINED.md` | Documentation |
| `FE_BE_DRIFT_REPORT.md` | Analysis |
| `FINAL_REPORT_ALL_PHASES.md` | Status |
| `FIRECRAWL_*.md` | Planning |
| `FORENSIC_AUDIT_REPORT.md` | Audit |
| `GITHUB_*.md` | Process |
| `IMMEDIATE_ACTIONS.md` | Planning |
| `IMPLEMENTATION_COMPLETE_SUMMARY.md` | Status |
| `INGESTION_PROOF_PACKET.md` | Proof |
| `ISSUES_FIXED_SUMMARY.md` | Status |
| `LANGFUSE_*.md` | Implementation |
| `LINKEDIN_TESTING_GUIDE.md` | Testing |
| `LINK_FIRST_*.md` | Implementation |
| `LLM_MODEL_SELECTION_GUIDE.md` | Documentation |
| `MIGRATION_*.md` | Planning |
| `ONBOARDING_*.md` | Implementation |
| `OPTION_C_COMPLETE.md` | Status |
| `PERSONA_5LAYER_*.md` | Implementation |
| `PERSONA_PIPELINE_VERIFICATION.md` | Verification |
| `PERSON_COMPLETENESS_V1_*.md` | Implementation |
| `PHASE*.md` | Planning/Status |
| `PLACEHOLDER_INVENTORY.md` | Documentation |
| `PR6_DEPLOYMENT_SUMMARY.md` | Status |
| `PROFILE_INTEGRATION_RECOMMENDATION.md` | Documentation |
| `PR_DELIVERABLES.md` | Documentation |
| `PUBLIC_RETRIEVAL_PROOF_PACKET.md` | Proof |
| `QUERY_REWRITER_*.md` | Documentation |
| `QUERY_REWRITING_*.md` | Implementation |
| `REPO_AUDIT_5LAYER_PERSONA.md` | Audit |
| `RENDER_DEPLOYMENT_FIXES.md` | Documentation |
| `RETRIEVAL_*.md` | Documentation |
| `SCOPE_CUT_PROPOSAL.md` | Planning |
| `SEMANTIC_CHUNKING_*.md` | Implementation |
| `SETUP_COMPLETE.md` | Status |
| `SIMPLIFICATION_CHANGELOG.md` | Documentation |
| `START_HERE_AUTOMATION.md` | Onboarding |
| `SYSTEM_AUDIT_AND_BUG_REPORT.md` | Audit |
| `TASK_PROGRESS.md` | Status |
| `TENANT_ISOLATION_ANALYSIS.md` | Analysis |
| `UI_UX_IMPLEMENTATION_PLAN.md` | Planning |
| `devlog.md` | Development log |
| `DUMPLING_MCP_*.md` | Documentation |
| `NAME_ONLY_DEEP_RESEARCH_ROLLOUT.md` | Planning |

### FLAG FOR REVIEW (Requires human decision)
Files that need review before action.

| Path | Concern | Recommendation |
|------|---------|----------------|
| `.env` | Contains hardcoded secrets | Create .env.example, gitignore .env |
| `context/` | Unknown contents | Review and classify |
| `eval/` | Evaluation framework | Keep but verify contents |
| `tests/` (root) | Test files | Review if duplicate of backend/tests |
| `deploy-staging/` | Staging config | Verify if still used |
| `.agent/mcp.json` | Modified in git | Review if should be tracked |
| `package/` | Package directory | Verify if used in deployment |

### MANUAL VERIFY SCRIPTS (Move to tools/manual_verify/)
One-off verification/proof scripts that are not part of runtime.

| Script | Purpose |
|--------|---------|
| `audit_current_state.py` | State audit |
| `check_linkedin_logs.py` | LinkedIn verification |
| `check_twin.py` | Twin check |
| `day1_map_to_test_creator.py` | Test generation |
| `day2_test_deletion.py` | Test cleanup |
| `generate_test_token.py` | Token generation |
| `inspect_twin_kb.py` | KB inspection |
| `live_chat_test.py` | Chat testing |
| `phase1_summary.py` | Results summarization |
| `test_chat_intent.py` | Intent testing |
| `test_intent_classification.py` | Classification testing |
| `test_live_conversation.py` | Conversation testing |
| `test_phase1_evaluation.py` | Phase 1 evaluation |
| `test_phase1_local.py` | Local testing |
| `test_phase3_summarization.py` | Summarization testing |
| `test_retrieval_direct.py` | Retrieval testing |
| `scripts/manual_verify_phase*.py` | Phase verification |
| `scripts/smoke_test_*.py` | Smoke tests |
| `scripts/test_*.py` | Various test scripts |
| `scripts/verify_*.py` | Verification scripts |
| `scripts/run_api_proof.py` | API proof |
| `scripts/check_*.py` | Various checks |
| `scripts/diagnose_*.py` | Diagnostics |

## Summary Statistics

| Category | Count |
|----------|-------|
| Root files total | ~130+ markdown files |
| Debug/test scripts | ~30+ |
| Proof artifacts | ~40+ files |
| Log files | ~15+ files |
| Cache/temp directories | ~10+ directories |
| Generated artifacts | ~50+ files |
