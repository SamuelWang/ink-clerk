import pytest

from shared.errors import GoogleApiError
from tools.import_google_doc import parse_doc_id


class TestParseDocId:
    def test_extracts_id_from_edit_url(self):
        url = "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit"
        assert parse_doc_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

    def test_extracts_id_from_bare_url(self):
        url = "https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/"
        assert parse_doc_id(url) == "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"

    def test_returns_bare_id_as_is(self):
        doc_id = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"
        assert parse_doc_id(doc_id) == doc_id

    def test_raises_google_api_error_when_docs_google_com_url_unmatched(self):
        with pytest.raises(GoogleApiError):
            parse_doc_id("https://docs.google.com/spreadsheets/d/abc123/edit")
