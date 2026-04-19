import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Signal, TrackedPerson
from app.schemas.signal import SignalResponse, SignalsListResponse, PersonInfo, CompanyInfo
from app.services.signal_scorer import days_since

logger = logging.getLogger(__name__)

router = APIRouter(tags=["signals"])


@router.get("/signals", response_model=SignalsListResponse)
async def get_signals(
    user_id: UUID,
    type: str | None = Query(None),
    flow: str | None = Query(None),
    urgency: str | None = Query(None),
    sort: str = Query("score"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    logger.info("get_signals | user_id=%s, type=%s, flow=%s, urgency=%s, sort=%s, limit=%d, offset=%d",
                user_id, type, flow, urgency, sort, limit, offset)

    query = select(Signal).where(Signal.user_id == user_id)

    if type:
        query = query.where(Signal.type == type)
    if flow:
        query = query.where(Signal.flow == flow)
    if urgency:
        query = query.where(Signal.urgency == urgency)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    if sort == "score":
        query = query.order_by(Signal.score.desc())
    else:
        query = query.order_by(Signal.created_at.desc())

    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    signals = result.scalars().all()

    response_signals = []
    for s in signals:
        person_result = await db.execute(
            select(TrackedPerson).where(TrackedPerson.id == s.person_id)
        )
        person = person_result.scalar_one_or_none()

        person_info = PersonInfo(
            name=person.name if person else "Unknown",
            title=person.title if person else None,
            linkedin_url=person.linkedin_url if person else None,
            previous_company=person.previous_company if person else None,
            new_company=person.current_company if person else None,
            transition_date=person.transition_date if person else None,
            days_since_transition=days_since(person.transition_date) if person and person.transition_date else None,
        )

        target = None
        if s.target_company:
            target = CompanyInfo(
                name=s.target_company,
                size=s.target_company_size,
                revenue_lower=s.target_company_revenue_lower,
                revenue_upper=s.target_company_revenue_upper,
            )

        response_signals.append(
            SignalResponse(
                id=s.id,
                type=s.type,
                flow=s.flow,
                person=person_info,
                target_company=target,
                score=s.score,
                urgency=s.urgency,
                reasoning=s.reasoning,
                suggested_action=s.suggested_action,
                is_read=s.is_read,
                created_at=s.created_at,
            )
        )

    logger.info("get_signals -> returning %d signals (total=%d)", len(response_signals), total)
    return SignalsListResponse(signals=response_signals, total=total)
