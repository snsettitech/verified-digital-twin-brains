# Manual Verification Tools

This directory contains one-off scripts and tools for manual verification, testing, debugging, and proof-of-concept work. These scripts are **not part of the runtime application** and should not be used in production deployments.

## Purpose

The scripts in this directory serve to:

1. **Verify functionality** - Manual verification of specific features or phases
2. **Debug issues** - Diagnostic scripts for troubleshooting
3. **Test integrations** - One-off tests for external services
4. **Generate proofs** - Evidence collection for verification
5. **Audit state** - Inspect and report on system state

## Script Categories

### Verification Scripts
- `manual_verify_phase*.py` - Phase-specific verification scripts
- `verify_*.py` - General verification scripts
- `check_*.py` - Status and health check scripts

### Testing Scripts
- `test_*.py` - Integration and manual test scripts
- `smoke_test_*.py` - Smoke test scripts
- `run_api_proof.py` - API verification

### Diagnostic Scripts
- `diagnose_*.py` - Diagnostic and troubleshooting
- `audit_current_state.py` - State auditing
- `inspect_twin_kb.py` - Knowledge base inspection

### Debug Utilities
- `generate_test_token.py` - Generate test JWT tokens
- `phase1_summary.py` - Summarize phase 1 results
- `day1_map_to_test_creator.py` - Test generation helper

## Usage

These scripts are typically run manually by developers or operators:

```bash
# Example: Run a verification script
cd tools/manual_verify
python verify_features.py

# Example: Generate a test token
python generate_test_token.py

# Example: Check system status
python check_worker_status.py
```

## Important Notes

1. **Not for production** - These scripts are for development/verification only
2. **No CI/CD integration** - Do not add these to automated pipelines
3. **May require setup** - Some scripts may need environment variables or local config
4. **Subject to change** - These scripts are maintained ad-hoc, not as stable APIs
5. **Review before use** - Check script contents before running, especially if modified

## When to Use

Use these scripts when:
- Debugging a specific issue in development
- Verifying a deployment manually
- Generating proof artifacts for review
- Running one-off diagnostics
- Testing integrations before full implementation

## When NOT to Use

Do not use these scripts for:
- Production monitoring (use proper observability tools)
- Automated testing (use proper test suite in `backend/tests/`)
- Regular operations (use operational runbooks in `docs/ops/`)
- Customer-facing features
