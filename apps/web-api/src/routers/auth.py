import os

from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

router = APIRouter(prefix="/auth")

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _build_flow() -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = f"{os.environ['PUBLIC_BASE_URL']}/auth/google/callback"
    return flow


@router.get("/google/start")
def google_start(session_id: str) -> RedirectResponse:
    flow = _build_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=session_id,
    )
    return RedirectResponse(authorization_url, status_code=302)
