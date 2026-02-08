def test_extract_text_from_pdf_handles_none_pages(monkeypatch):
    from modules import ingestion

    class _Page:
        def __init__(self, text):
            self._text = text

        def extract_text(self):
            return self._text

    class _Reader:
        def __init__(self, *_args, **_kwargs):
            self.pages = [_Page(None), _Page("LinkedIn profile summary"), _Page("")]

    monkeypatch.setattr(ingestion, "PdfReader", _Reader)

    text = ingestion.extract_text_from_pdf("dummy.pdf")
    assert text == "LinkedIn profile summary"
