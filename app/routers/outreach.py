import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Signal, TrackedPerson, OutreachDraft, User
from app.schemas.outreach import OutreachRequest, OutreachResponse
from app.services.claude import claude_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["outreach"])


@router.post("/outreach", response_model=OutreachResponse)
async def generate_outreach(request: OutreachRequest, db: AsyncSession = Depends(get_db)):
    logger.info("======== OUTREACH request | signal_id=%s ========", request.signal_id)

    signal_result = await db.execute(
        select(Signal).where(Signal.id == request.signal_id)
    )
    signal = signal_result.scalar_one_or_none()
    if not signal:
        logger.warning("Outreach requested for unknown signal_id=%s", request.signal_id)
        raise HTTPException(status_code=404, detail="Signal not found")
    logger.info("Signal found: type=%s, score=%s, target=%s", signal.type, signal.score, signal.target_company)

    person_result = await db.execute(
        select(TrackedPerson).where(TrackedPerson.id == signal.person_id)
    )
    person = person_result.scalar_one_or_none()
    if not person:
        logger.warning("Person not found for signal person_id=%s", signal.person_id)
        raise HTTPException(status_code=404, detail="Person not found")
    logger.info("Person: %s (%s), %s -> %s", person.name, person.title,
                person.previous_company, person.current_company)

    user_result = await db.execute(
        select(User).where(User.id == signal.user_id)
    )
    user = user_result.scalar_one_or_none()

    outreach_data = await claude_client.generate_outreach(
        person_name=person.name,
        person_title=person.title or "",
        previous_company=person.previous_company or "",
        new_company=person.current_company or "",
        signal_type=signal.type,
        product_name=user.product_name,
        product_description=user.product_description or "",
        reasoning=signal.reasoning or "",
    )

    draft = OutreachDraft(
        signal_id=signal.id,
        subject_line=outreach_data.get("subject_line", ""),
        email_body=outreach_data.get("email_body", ""),
        talking_points=outreach_data.get("talking_points", []),
        tone=outreach_data.get("tone", "warm_reconnect"),
        timing_recommendation=outreach_data.get("timing_recommendation", "Send within 7 days"),
    )
    db.add(draft)
    await db.commit()
    await db.refresh(draft)

    logger.info("======== OUTREACH complete | draft_id=%s, subject=%s, tone=%s ========",
                draft.id, draft.subject_line, draft.tone)

    return OutreachResponse(
        id=draft.id,
        signal_id=draft.signal_id,
        subject_line=draft.subject_line,
        email_body=draft.email_body,
        talking_points=draft.talking_points or [],
        tone=draft.tone,
        timing_recommendation=draft.timing_recommendation,
    )
