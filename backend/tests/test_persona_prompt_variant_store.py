from types import SimpleNamespace

from modules.persona_prompt_variant_store import (
    DEFAULT_PERSONA_PROMPT_VARIANT,
    get_active_variant_id_or_default,
    list_persona_prompt_variants,
)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "persona_prompt_variants"
        return _FakeQuery(self._rows)


def test_list_persona_prompt_variants_returns_rows(monkeypatch):
    rows = [{"variant_id": "compact_v1", "status": "draft"}]
    monkeypatch.setattr("modules.persona_prompt_variant_store.supabase", _FakeSupabase(rows))

    result = list_persona_prompt_variants("twin-1")
    assert len(result) == 1
    assert result[0]["variant_id"] == "compact_v1"


def test_get_active_variant_id_falls_back_to_default(monkeypatch):
    monkeypatch.setattr("modules.persona_prompt_variant_store.supabase", _FakeSupabase([]))
    assert get_active_variant_id_or_default("twin-1") == DEFAULT_PERSONA_PROMPT_VARIANT
