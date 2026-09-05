"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .body_limit_middleware import RequestBodyLimitMiddleware
from .contracts import ApiRuntime
from .error_handlers import register_error_handlers
from .request_id_middleware import RequestIdMiddleware
from .routers import (
    auth,
    campaigns,
    health,
    jobs,
    participants,
    recordings,
    results,
    samples,
)

_MULTIPART_OVERHEAD_BYTES = 1024 * 1024


def create_api_app(runtime: ApiRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime.start()
        try:
            yield
        finally:
            runtime.shutdown()

    app = FastAPI(
        title="NoteKeeper Local API",
        version="1.0.0",
        description=(
            "Development-only HTTP adapter backed by local authentication, "
            "SQLite, filesystem artifacts, and the local process queue."
        ),
        lifespan=lifespan,
    )
    app.state.api_runtime = runtime
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(campaigns.router)
    app.include_router(participants.router)
    app.include_router(samples.router)
    app.include_router(recordings.router)
    app.include_router(jobs.router)
    app.include_router(results.router)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=runtime.upload_max_bytes + _MULTIPART_OVERHEAD_BYTES,
    )
    return app


__all__ = ["create_api_app"]
