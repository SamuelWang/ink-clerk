import pytest

from shared.frontmatter import parse, write


class TestParse:
    def test_crlf_line_endings_parsed_correctly(self):
        text = "---\r\ntitle: Hello\r\nauthor: Sam\r\n---\r\n\r\nBody text here."
        meta, body = parse(text)
        assert meta == {"title": "Hello", "author": "Sam"}
        assert body == "Body text here."

    def test_valid_frontmatter_splits_meta_and_body(self):
        text = "---\ntitle: Hello\nauthor: Sam\n---\n\nBody text here."
        meta, body = parse(text)
        assert meta == {"title": "Hello", "author": "Sam"}
        assert body == "Body text here."

    def test_no_frontmatter_returns_empty_meta_and_original_text(self):
        text = "Just some plain text."
        meta, body = parse(text)
        assert meta == {}
        assert body == "Just some plain text."

    def test_malformed_yaml_returns_empty_meta_and_original_text(self):
        text = "---\n: invalid: yaml: [\n---\n\nBody."
        with pytest.warns(UserWarning, match="Malformed YAML frontmatter"):
            meta, body = parse(text)
        assert meta == {}
        assert body == text

    def test_frontmatter_with_empty_body_returns_empty_string_not_none(self):
        text = "---\nid: abc\n---\n"
        meta, body = parse(text)
        assert meta == {"id": "abc"}
        assert body == ""
        assert body is not None

    def test_body_leading_newline_stripped(self):
        text = "---\nkey: val\n---\n\nActual body."
        _, body = parse(text)
        assert body == "Actual body."
        assert not body.startswith("\n")

    def test_draft_body_no_frontmatter_returns_empty_meta(self):
        draft_body = "This is the draft content.\nNo frontmatter here."
        meta, body = parse(draft_body)
        assert meta == {}
        assert body == draft_body


class TestWrite:
    def test_crlf_body_normalized_to_lf(self):
        meta = {"id": "1"}
        result = write(meta, "line1\r\nline2\r\n")
        assert "\r" not in result

    def test_empty_meta_returns_body_only(self):
        assert write({}, "just a body") == "just a body"

    def test_round_trip_plain_text(self):
        text = "plain text with no frontmatter"
        assert write(*parse(text)) == text

    def test_round_trip(self):
        original = "---\nauthor: Sam\ntitle: Hello\n---\n\nBody text here."
        assert write(*parse(original)) == original

    def test_cjk_values_written_as_raw_unicode_not_escaped(self):
        meta = {"title": "會議記錄"}
        body = "Some content."
        result = write(meta, body)
        assert "會議記錄" in result
        assert "\\u" not in result

    def test_write_produces_correct_structure(self):
        meta = {"id": "123", "version": 1}
        body = "Hello world."
        result = write(meta, body)
        assert result.startswith("---\n")
        assert "\n---\n\n" in result
        assert result.endswith("Hello world.")

    def test_round_trip_empty_body(self):
        original = "---\nid: abc\n---\n\n"
        assert write(*parse(original)) == original
