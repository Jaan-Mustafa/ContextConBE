import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Customer, Competitor
from app.schemas.scan import ScanRequest, ScanResponse, ScanBreakdown
from app.services.champion_tracker import scan_customers
from app.services.competitor_analyzer import scan_competitor_customers

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])


@router.post("/scan", response_model=ScanResponse)
async def run_scan(request: ScanRequest, db: AsyncSession = Depends(get_db)):
    scan_start = time.perf_counter()
    logger.info("======== SCAN START | user_id=%s ========", request.user_id)

    result = await db.execute(
        select(User).where(User.id == request.user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info("User found: %s (%s)", user.email, user.product_name)

    customers_result = await db.execute(
        select(Customer).where(Customer.user_id == user.id)
    )
    customers = list(customers_result.scalars().all())

    competitors_result = await db.execute(
        select(Competitor).where(Competitor.user_id == user.id)
    )
    competitors = list(competitors_result.scalars().all())

    logger.info("Found %d customers, %d competitors to scan", len(customers), len(competitors))

    champion_result = await scan_customers(
        db=db,
        user_id=user.id,
        customers=customers,
        product_name=user.product_name,
        product_description=user.product_description or "",
    )

    competitor_result = await scan_competitor_customers(
        db=db,
        user_id=user.id,
        competitors=competitors,
        product_name=user.product_name,
        product_description=user.product_description or "",
    )

    await db.commit()

    all_signals = champion_result["signals"] + competitor_result["signals"]
    scan_elapsed = (time.perf_counter() - scan_start) * 1000

    breakdown = ScanBreakdown(
        new_leads=sum(1 for s in all_signals if s.type == "new_lead"),
        churn_risks=sum(1 for s in all_signals if s.type == "churn_risk"),
        competitive_displacements=sum(1 for s in all_signals if s.type == "competitive_displacement"),
    )

    logger.info(
        "======== SCAN COMPLETE (%.1fms) | people=%d, signals=%d "
        "(leads=%d, churn=%d, displacement=%d) ========",
        scan_elapsed,
        champion_result["people_tracked"] + competitor_result["people_tracked"],
        len(all_signals),
        breakdown.new_leads,
        breakdown.churn_risks,
        breakdown.competitive_displacements,
    )

    return ScanResponse(
        people_tracked=champion_result["people_tracked"] + competitor_result["people_tracked"],
        signals_generated=len(all_signals),
        competitor_customers_discovered=competitor_result["competitor_customers_discovered"],
        breakdown=breakdown,
    )
