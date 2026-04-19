import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Customer, Competitor
from app.schemas.onboard import OnboardRequest, OnboardResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["onboard"])


@router.post("/onboard", response_model=OnboardResponse, status_code=201)
async def onboard(request: OnboardRequest, db: AsyncSession = Depends(get_db)):
    logger.info("======== ONBOARD request | email=%s, company=%s, product=%s ========",
                request.email, request.company_name, request.product_name)
    logger.info("Customers: %d, Competitors: %d", len(request.customers), len(request.competitors))

    existing = await db.execute(select(User).where(User.email == request.email))
    user = existing.scalar_one_or_none()

    if user:
        logger.info("Updating existing user: %s (id=%s)", request.email, user.id)
        user.company_name = request.company_name
        user.product_name = request.product_name
        user.product_description = request.product_description
    else:
        logger.info("Creating new user: %s", request.email)
        user = User(
            email=request.email,
            company_name=request.company_name,
            product_name=request.product_name,
            product_description=request.product_description,
        )
        db.add(user)
        await db.flush()

    for c in request.customers:
        customer = Customer(
            user_id=user.id,
            company_name=c.company_name,
            linkedin_url=c.linkedin_url,
        )
        db.add(customer)

    for comp in request.competitors:
        competitor = Competitor(
            user_id=user.id,
            company_name=comp.company_name,
            product_name=comp.product_name,
        )
        db.add(competitor)

    await db.commit()

    logger.info("======== ONBOARD complete | user_id=%s, customers=%d, competitors=%d ========",
                user.id, len(request.customers), len(request.competitors))

    return OnboardResponse(
        user_id=user.id,
        customers_tracked=len(request.customers),
        competitors_tracked=len(request.competitors),
        message="Onboarding complete. Run a scan to discover signals.",
    )
