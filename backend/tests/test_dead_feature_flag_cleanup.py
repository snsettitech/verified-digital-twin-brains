from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_text(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_dead_backend_flag_surfaces_stay_deleted():
    stale_terms = ("ENABLE_VC_ROUTES", "VC_ROUTES_ENABLED", "GRAPH_RAG_ENABLED")
    target_files = [
        "AGENTS.md",
        "backend/.env.example",
        "backend/main.py",
        "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md",
        "docs/architecture/codebase-summary.md",
        "docs/architecture/system-overview.md",
        "docs/architecture/VC_IMPLEMENTATION_SUMMARY.md",
        "docs/architecture/VC_SPECIALIZATION_ARCHITECTURE.md",
        "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md",
        "docs/restructure/BACKEND_DELETION_DEFER_PLAN.md",
        "docs/restructure/BACKEND_RESTRUCTURE_OVERVIEW.md",
        "docs/restructure/BACKEND_ROUTE_INVENTORY.md",
    ]

    offenders = {}
    for relative_path in target_files:
        content = _read_text(relative_path)
        hits = [term for term in stale_terms if term in content]
        if hits:
            offenders[relative_path] = hits

    assert not offenders, f"Stale backend flag references remain: {offenders}"
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()


def test_dead_frontend_flag_surfaces_stay_deleted():
    target_files = [
        "frontend/.env.example",
        "frontend/app/layout.tsx",
        "frontend/lib/features/runtimeFlags.ts",
    ]
    stale_terms = (
        "FeatureFlagProvider",
        "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE",
        "NEXT_PUBLIC_FF_SOURCE_LABELING",
        "officeHoursMode",
        "sourceLabeling",
        "useFeatureFlags",
    )

    offenders = {}
    for relative_path in target_files:
        content = _read_text(relative_path)
        hits = [term for term in stale_terms if term in content]
        if hits:
            offenders[relative_path] = hits

    assert not offenders, f"Stale frontend flag references remain: {offenders}"
    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
