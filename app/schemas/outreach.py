from uuid import UUID

from pydantic import BaseModel


class OutreachRequest(BaseModel):
    signal_id: UUID


class OutreachResponse(BaseModel):
    id: UUID
    signal_id: UUID
    subject_line: str
    email_body: str
    talking_points: list[str]
    tone: str
    timing_recommendation: str
