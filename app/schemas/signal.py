from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class PersonInfo(BaseModel):
    name: str
    title: str | None = None
    linkedin_url: str | None = None
    previous_company: str | None = None
    new_company: str | None = None
    transition_date: datetime | None = None
    days_since_transition: int | None = None


class CompanyInfo(BaseModel):
    name: str | None = None
    size: int | None = None
    revenue_lower: int | None = None
    revenue_upper: int | None = None


class SignalResponse(BaseModel):
    id: UUID
    type: str
    flow: str
    person: PersonInfo
    target_company: CompanyInfo | None = None
    score: int
    urgency: str
    reasoning: str | None = None
    suggested_action: str | None = None
    is_read: bool = False
    created_at: datetime


class SignalsListResponse(BaseModel):
    signals: list[SignalResponse]
    total: int
