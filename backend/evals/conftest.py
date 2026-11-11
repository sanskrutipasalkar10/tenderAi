import pytest

from app.pipeline import reduce_pass


@pytest.fixture(autouse=True)
def _no_page_reads(monkeypatch) -> None:
    """The golden-set fake sessions model chunk facts, not `pages` rows — the page-
    reading checks (consortium policy, project brief) have their own unit tests."""
    monkeypatch.setattr(reduce_pass, "load_tender_pages", lambda db, document: [])
