"""
Regression tests for the _ensure_closing_question post-processing guard.

This function guarantees every agent response ends with exactly one question
so the conversation stays interactive.
"""

from modules.agent import _ensure_closing_question


class TestEnsureClosingQuestion:
    """Tests for _ensure_closing_question."""

    def test_already_ends_with_question(self):
        text = "Here is some info. What do you think?"
        assert _ensure_closing_question(text, "test") == text

    def test_appends_fallback_when_no_question(self):
        text = "Here is some information about the topic."
        result = _ensure_closing_question(text, "test")
        assert result.endswith("?")
        assert "What aspect of this would be most useful to go deeper on?" in result

    def test_empty_string_returns_unchanged(self):
        assert _ensure_closing_question("", "test") == ""

    def test_none_returns_unchanged(self):
        assert _ensure_closing_question(None, "test") is None

    def test_whitespace_only_returns_unchanged(self):
        assert _ensure_closing_question("   ", "test") == "   "

    def test_multiple_sentences_last_is_question(self):
        text = "First sentence. Second sentence. Is this clear?"
        assert _ensure_closing_question(text, "test") == text

    def test_multiple_sentences_last_not_question(self):
        text = "First sentence. This is a statement."
        result = _ensure_closing_question(text, "test")
        assert result.endswith("?")

    def test_exclamation_mark_gets_fallback(self):
        text = "Great news!"
        result = _ensure_closing_question(text, "test")
        assert result.endswith("?")

    def test_preserves_original_text(self):
        text = "Here is some information."
        result = _ensure_closing_question(text, "test")
        assert result.startswith("Here is some information.")
