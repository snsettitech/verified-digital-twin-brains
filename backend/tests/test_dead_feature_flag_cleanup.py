from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def read_repo_file(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_dead_backend_feature_flag_surfaces_stay_removed() -> None:
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in read_repo_file("backend/routers/chat.py")
    assert "RUNTIME_SUPPORT_POLICY_ENABLED" not in read_repo_file("backend/README.md")
    assert "GRAPH_RAG_ENABLED" not in read_repo_file("docs/ARCHITECTURE_INGESTION_RETRIEVAL.md")
    assert "GRAPH_RAG_ENABLED" not in read_repo_file("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in read_repo_file(".env.example")
    assert "RUNTIME_CONFIDENCE_GATE_ENABLED" not in read_repo_file("backend/.env.example")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("backend/main.py")
    assert "VC_ROUTES_ENABLED" not in read_repo_file("backend/main.py")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("backend/.env.example")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("AGENTS.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/ops/PRODUCTION_DEPLOYMENT_RUNBOOK.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/architecture/system-overview.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/architecture/codebase-summary.md")
    assert "vc_routes.py" not in read_repo_file("docs/architecture/system-overview.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/restructure/BACKEND_ROUTE_INVENTORY.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/restructure/BACKEND_RESTRUCTURE_OVERVIEW.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/restructure/BACKEND_DELETION_DEFER_PLAN.md")
    assert "ENABLE_VC_ROUTES" not in read_repo_file("docs/audit/issues/ISSUE-003-enable-stable-features-by-default.md")
    assert not (REPO_ROOT / "backend/tests/test_graphrag_feature_flag.py").exists()


def test_dead_frontend_feature_flag_plumbing_stays_removed() -> None:
    assert not (REPO_ROOT / "frontend/lib/features/FeatureFlags.tsx").exists()
    assert "FeatureFlagProvider" not in read_repo_file("frontend/app/layout.tsx")

    runtime_flags = read_repo_file("frontend/lib/features/runtimeFlags.ts")
    assert "sourceLabeling" not in runtime_flags
    assert "officeHoursMode" not in runtime_flags
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in runtime_flags
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in runtime_flags

    frontend_env = read_repo_file("frontend/.env.example")
    assert "NEXT_PUBLIC_FF_SOURCE_LABELING" not in frontend_env
    assert "NEXT_PUBLIC_FF_OFFICE_HOURS_MODE" not in frontend_env
