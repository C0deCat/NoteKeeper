"""Map application, domain, and transport failures to one error envelope."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from notekeeper.application import (
    AuthenticationRequiredError,
    AuthorizationError,
    InvalidCredentialsError,
    InvalidOperationError,
    NotFoundError,
    PortExecutionError,
    UserAlreadyExistsError,
)
from notekeeper.domain import DomainError

from .errors import ApiError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error_handler)
    app.add_exception_handler(
        AuthenticationRequiredError,
        _authentication_handler,
    )
    app.add_exception_handler(InvalidCredentialsError, _authentication_handler)
    app.add_exception_handler(AuthorizationError, _authorization_handler)
    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.add_exception_handler(UserAlreadyExistsError, _conflict_handler)
    app.add_exception_handler(InvalidOperationError, _conflict_handler)
    app.add_exception_handler(PortExecutionError, _port_handler)
    app.add_exception_handler(DomainError, _domain_handler)
    app.add_exception_handler(ValueError, _value_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(HTTPException, _http_handler)
    app.add_exception_handler(Exception, _unexpected_handler)


async def _api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = exc
    assert isinstance(error, ApiError)
    return _response(
        request,
        error.status_code,
        error.code,
        error.message,
        details=error.details,
        headers=error.headers,
    )


async def _authentication_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(
        request,
        401,
        "authentication_required",
        "Valid authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _authorization_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, 403, "forbidden", "Operation is not permitted")


async def _not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, 404, "not_found", "Resource was not found")


async def _conflict_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, 409, "conflict", str(exc))


async def _port_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.warning(
        "API dependency unavailable request_id=%s",
        _request_id(request),
        exc_info=exc,
    )
    return _response(
        request,
        503,
        "service_unavailable",
        "A required local service is unavailable",
    )


async def _domain_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, 422, "validation_error", str(exc))


async def _value_handler(request: Request, exc: Exception) -> JSONResponse:
    return _response(request, 422, "validation_error", str(exc))


async def _validation_handler(request: Request, exc: Exception) -> JSONResponse:
    validation = exc
    assert isinstance(validation, RequestValidationError)
    return _response(
        request,
        422,
        "validation_error",
        "Request validation failed",
        details={"errors": jsonable_encoder(validation.errors())},
    )


async def _http_handler(request: Request, exc: Exception) -> JSONResponse:
    http_error = exc
    assert isinstance(http_error, HTTPException)
    code = "not_found" if http_error.status_code == 404 else "http_error"
    message = (
        "Resource was not found"
        if http_error.status_code == 404
        else str(http_error.detail)
    )
    return _response(
        request,
        http_error.status_code,
        code,
        message,
        headers=dict(http_error.headers or {}),
    )


async def _unexpected_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unexpected API failure request_id=%s",
        _request_id(request),
        exc_info=exc,
    )
    return _response(
        request,
        500,
        "internal_error",
        "An unexpected error occurred",
    )


def _response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    *,
    details: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
                "details": details if details is not None else {},
            }
        },
        headers=headers,
    )


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


__all__ = ["register_error_handlers"]
