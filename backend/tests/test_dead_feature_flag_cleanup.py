from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


LIVE_SURFACE_LITERALS = {
    "backend/main.py": (
        "ENABLE_VC_ROUTES",
        "VC_ROUTES_ENABLED",
    ),
    "backend/routers/chat.py": (
        "RUNTIME_SUPPORT_POLICY_ENABLED",
    ),
    "backend/modules/agent.py": (
        "ROUTER_FORCE_RETRIEVAL_WITH_KNOWLEDGE",
    ),
    "backend/README.md": (
        "RUNTIME_SUPPORT_POLICY_ENABLED",
    ),
    ".env.example": (
        "RUNTIME_CONFIDENCE_GATE_ENABLED",
    ),
    "backend/.env.example": (
        "ENABLE_VC_ROUTES",
        "RUNTIME_CONFIDENCE_GATE_ENABLED",
    ),
    "frontend/.env.example": (
        "NEXT_PUBLIC_FF_SOURCE_LABELING",
        "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE",
    ),
    "frontend/app/layout.tsx": (
        "FeatureFlagProvider",
    ),
    "frontend/lib/features/runtimeFlags.ts": (
        "sourceLabeling",
        "officeHoursMode",
    ),
    "docs/ARCHITECTURE_INGESTION_RETRIEVAL.md": (
        "GRAPH_RAG_ENABLED",
    ),
    "docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md": (
        "GRAPH_RAG_ENABLED",
        "ENABLE_VC_ROUTES",
    ),
    "AGENTS.md": (
        "ENABLE_VC_ROUTES",
        "VC_ROUTES_ENABLED",
    ),
    "docs/architecture/system-overview.md": (
        "ENABLE_VC_ROUTES",
        "vc_routes.py",
    ),
    "docs/architecture/codebase-summary.md": (
        "ENABLE_VC_ROUTES",
        "api/vc_routes.py",
    ),
    "docs/architecture/VC_SPECIALIZATION_ARCHITECTURE.md": (
        "ENABLE_VC_ROUTES",
        "VC_ROUTES_ENABLED",
        "api/vc_routes.py",
    ),
    "docs/architecture/VC_IMPLEMENTATION_SUMMARY.md": (
        "ENABLE_VC_ROUTES",
        "VC_ROUTES_ENABLED",
        "api/vc_routes.py",
    ),
    "docs/restructure/BACKEND_ROUTE_INVENTORY.md": (
        "ENABLE_VC_ROUTES",
        "api/vc_routes.py",
    ),
    "docs/restructure/BACKEND_RESTRUCTURE_OVERVIEW.md": (
        "ENABLE_VC_ROUTES",
        "api/vc_routes.py",
    ),
    "docs/restructure/BACKEND_DELETION_DEFER_PLAN.md": (
        "ENABLE_VC_ROUTES",
        "api/vc_routes.py",
    ),
    "docs/restructure/BACKEND_PR_EXECUTION_PLAN.md": (
        "api/vc_routes.py",
    ),
    "docs/restructure/BACKEND_KEEP_TWEAK_REFACTOR_DELETE.md": (
        "api/vc_routes.py",
    ),
    "docs/restructure/BACKEND_API_CONTRACT_V1.md": (
        "api/vc_routes.py",
    ),
}


def _read_text(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_removed_feature_flag_literals_are_absent_from_live_surfaces():
    for relative_path, removed_literals in LIVE_SURFACE_LITERALS.items():
        file_text = _read_text(relative_path)
        for removed_literal in removed_literals:
            assert (
                removed_literal not in file_text
            ), f"{removed_literal} still present in {relative_path}"


def test_obsolete_graphrag_flag_test_file_is_deleted():
    assert not (PROJECT_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()


def test_obsolete_frontend_feature_flag_provider_is_deleted():
    assert not (PROJECT_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
