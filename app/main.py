from __future__ import annotations

from pathlib import Path
from typing import Any, cast, Callable, Awaitable

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from app.config.settings import get_settings
from app.logger import logger
from app.modules.auth import router as auth_router
from app.modules.invoices.router import router as invoices_router
settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")


app.add_middleware(
    cast(Any, CORSMiddleware),
    allow_origins=settings.parsed_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def debug_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]):
    body = await request.body()
    logger.debug(
        "REQUEST ARRIVED method=%s url=%s query=%s content_type=%s body_len=%s",
        request.method,
        request.url,
        dict(request.query_params),
        request.headers.get("content-type"),
        len(body),
    )
    response: Response = await call_next(request)
    logger.debug("RESPONSE SENT status_code=%s headers=%s", response.status_code, dict(response.headers))
    return response

api_prefix = "/api" if settings.use_proxy else ""

app.include_router(auth_router, prefix=api_prefix, tags=["auth"])
app.include_router(invoices_router, prefix=api_prefix, tags=["invoices"])

public_data_path = Path(settings.public_data_dir)
if public_data_path.exists():
    app.mount("/data", StaticFiles(directory=public_data_path), name="data")
