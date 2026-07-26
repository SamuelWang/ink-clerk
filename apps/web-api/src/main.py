import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import import_session

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("WEB_APP_ORIGIN", "http://localhost:5173")],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(import_session.router)
