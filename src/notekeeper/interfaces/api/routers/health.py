"""Unauthenticated service health route."""

from fastapi import APIRouter

router = APIRouter(tags=["service"])


@router.get("/health", operation_id="get_health")
def get_health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "notekeeper",
        "api_version": "v1",
        "profile": "local",
    }


__all__ = ["router"]
