"""Shared HTTP schema DTOs."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ErrorBody(ApiSchema):
    code: str
    message: str
    request_id: str
    details: object = Field(default_factory=dict)


class ErrorResponse(ApiSchema):
    error: ErrorBody


ItemT = TypeVar("ItemT")


class ItemsResponse(ApiSchema, Generic[ItemT]):
    items: list[ItemT]


__all__ = ["ApiSchema", "ErrorBody", "ErrorResponse", "ItemsResponse"]
