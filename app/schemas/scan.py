from uuid import UUID

from pydantic import BaseModel


class ScanRequest(BaseModel):
    user_id: UUID


class ScanBreakdown(BaseModel):
    new_leads: int = 0
    churn_risks: int = 0
    competitive_displacements: int = 0


class ScanResponse(BaseModel):
    people_tracked: int
    signals_generated: int
    competitor_customers_discovered: int
    breakdown: ScanBreakdown


class ScanStatusResponse(BaseModel):
    status: str  # "idle" | "scanning" | "done" | "error"
    progress: str = ""
    people_tracked: int = 0
    signals_generated: int = 0
    competitor_customers_discovered: int = 0
    breakdown: ScanBreakdown = ScanBreakdown()
    error: str | None = None
