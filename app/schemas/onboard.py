from uuid import UUID

from pydantic import BaseModel, EmailStr


class CustomerInput(BaseModel):
    company_name: str
    linkedin_url: str | None = None


class CompetitorInput(BaseModel):
    company_name: str
    product_name: str


class OnboardRequest(BaseModel):
    email: str
    company_name: str
    product_name: str
    product_description: str | None = None
    customers: list[CustomerInput] = []
    competitors: list[CompetitorInput] = []


class OnboardResponse(BaseModel):
    user_id: UUID
    customers_tracked: int
    competitors_tracked: int
    message: str
