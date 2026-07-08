import importlib
import sys


def test_feature_flag_summary_omits_vc_routes(monkeypatch, capsys):
    monkeypatch.setenv("DEV_MODE", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
    monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")

    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    capsys.readouterr()

    main.print_feature_flag_summary()

    output = capsys.readouterr().out

    assert "Realtime Ingestion: ENABLED" in output
    assert "Enhanced Ingestion: ENABLED" in output
    assert "advisor retrieval:   ENABLED" in output
    assert "Deep Research:      ENABLED" in output
    assert "Name->Research JSON:ENABLED" in output
    assert "VC Routes:" not in output
