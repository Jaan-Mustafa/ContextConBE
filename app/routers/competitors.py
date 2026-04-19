import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Competitor, CompetitorCustomer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["competitors"])


@router.get("/competitors/customers")
async def get_competitor_customers(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    logger.info("get_competitor_customers | user_id=%s", user_id)

    competitors_result = await db.execute(
        select(Competitor).where(Competitor.user_id == user_id)
    )
    competitors = competitors_result.scalars().all()

    response = []
    for comp in competitors:
        customers_result = await db.execute(
            select(CompetitorCustomer).where(CompetitorCustomer.competitor_id == comp.id)
        )
        customers = customers_result.scalars().all()

        response.append({
            "name": comp.company_name,
            "product_name": comp.product_name,
            "discovered_customers": [
                {
                    "company_name": c.company_name,
                    "confidence": c.confidence,
                    "discovered_via": c.discovered_via,
                }
                for c in customers
            ],
            "total_customers_found": len(customers),
        })

    total_customers = sum(item["total_customers_found"] for item in response)
    logger.info("get_competitor_customers -> %d competitors, %d total discovered customers",
                len(response), total_customers)
    return {"competitors": response}
