from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class ApiListResponse(BaseModel):
    items: list[Any]
    total: int


class OptionItem(BaseModel):
    label: str
    value: str


class UserSummary(BaseModel):
    id: UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    timezone: str = "Europe/Kaliningrad"
    locale: str = "ru-RU"
    created_at: datetime
