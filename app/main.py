from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from app.config.settings import get_settings
from app.modules.auth import router as auth_router

settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    cast(Any, CORSMiddleware),
    allow_origins=settings.parsed_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

public_data_path = Path(settings.public_data_dir)
if public_data_path.exists():
    app.mount("/data", StaticFiles(directory=public_data_path), name="data")
