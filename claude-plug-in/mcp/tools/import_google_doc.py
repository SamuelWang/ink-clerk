import re

from shared.errors import GoogleApiError

_DOC_ID_URL_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")


def parse_doc_id(google_doc_url_or_id: str) -> str:
    match = _DOC_ID_URL_RE.search(google_doc_url_or_id)
    if match:
        return match.group(1)
    if "docs.google.com" in google_doc_url_or_id:
        raise GoogleApiError("Cannot parse Google Doc URL")
    return google_doc_url_or_id
