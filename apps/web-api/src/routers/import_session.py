import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/import/google-doc")

SESSION_TTL_SECONDS = 10 * 60

_session_store: dict[str, dict] = {}


class CompleteRequest(BaseModel):
    access_token: str
    expires_in: int
    file_id: str
    file_name: str
    resource_key: str = ""


@router.post("/session/{session_id}/complete")
def complete_session(session_id: str, body: CompleteRequest) -> JSONResponse:
    _session_store[session_id] = {
        "status": "ready",
        "access_token": body.access_token,
        "expires_in": body.expires_in,
        "file_id": body.file_id,
        "file_name": body.file_name,
        "resource_key": body.resource_key,
        "created_at": time.time(),
    }
    return JSONResponse(content={"status": "ready"})


@router.get("/session/{session_id}")
def get_session(session_id: str) -> dict:
    entry = _session_store.get(session_id)
    if entry is None:
        return {"status": "pending"}
    if entry["status"] == "expired":
        return {"status": "expired"}

    age = time.time() - entry["created_at"]
    if age > SESSION_TTL_SECONDS:
        _session_store[session_id] = {"status": "expired"}
        return {"status": "expired"}

    # Single-claim: tombstone now so any future poll for this session_id (a
    # duplicate retry, or a poll long after this one) sees "expired" instead
    # of re-issuing this access token.
    _session_store[session_id] = {"status": "expired"}
    return {
        "status": "ready",
        "access_token": entry["access_token"],
        "expires_in": entry["expires_in"],
        "file_id": entry["file_id"],
        "file_name": entry["file_name"],
        "resource_key": entry.get("resource_key", ""),
    }
