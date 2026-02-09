from types import SimpleNamespace

from modules.persona_module_store import list_runtime_modules_for_intent


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def in_(self, *_args, **_kwargs):
        return self

    def or_(self, *_args, **_kwargs):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def gte(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        return SimpleNamespace(data=self._rows)


class _FakeSupabase:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "persona_modules"
        return _FakeQuery(self._rows)


def test_list_runtime_modules_for_intent_filters_and_dedupes(monkeypatch):
    rows = [
        {
            "module_id": "procedural.style.one",
            "intent_label": "advice_or_stance",
            "module_data": {
                "do": ["ask_one_clarifying_question"],
                "say_style": {"tone": "direct"},
                "priority": 20,
            },
            "status": "draft",
            "confidence": 0.9,
        },
        {
            # Duplicate id should be ignored after first occurrence.
            "module_id": "procedural.style.one",
            "intent_label": "advice_or_stance",
            "module_data": {"do": ["old_rule"], "priority": 80},
            "status": "draft",
            "confidence": 0.6,
        },
        {
            "module_id": "procedural.factual.two",
            "intent_label": "factual_with_evidence",
            "module_data": {"do": ["retrieve_evidence_first"], "priority": 10},
            "status": "active",
            "confidence": 0.95,
        },
    ]
    monkeypatch.setattr("modules.persona_module_store.supabase", _FakeSupabase(rows))

    modules = list_runtime_modules_for_intent(
        twin_id="twin-1",
        intent_label="advice_or_stance",
        limit=5,
        include_draft=True,
        min_confidence=0.65,
    )

    assert len(modules) == 1
    assert modules[0].id == "procedural.style.one"
    assert modules[0].do == ["ask_one_clarifying_question"]
    assert modules[0].intent_labels == ["advice_or_stance"]

