import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def calculate_score(
    title: str | None,
    days_since_transition: int,
    target_company_size: int | None,
    person_used_product: bool = True,
    company_raised_recently: bool = False,
    headcount_growing: bool = False,
) -> int:
    score = 0.0

    seniority_scores = {
        "cto": 100, "ceo": 100, "co-founder": 100, "founder": 100,
        "vp": 80, "vice president": 80,
        "director": 60,
        "head": 50,
        "senior manager": 30, "manager": 20,
    }
    title_lower = (title or "").lower()
    seniority = 20
    for key, val in seniority_scores.items():
        if key in title_lower:
            seniority = val
            break
    score += seniority * 0.30

    if days_since_transition < 14:
        recency = 100
    elif days_since_transition < 30:
        recency = 80
    elif days_since_transition < 60:
        recency = 50
    elif days_since_transition < 90:
        recency = 30
    else:
        recency = 10
    score += recency * 0.25

    headcount = target_company_size or 0
    if headcount > 1000:
        size = 100
    elif headcount > 500:
        size = 80
    elif headcount > 100:
        size = 60
    elif headcount > 50:
        size = 40
    else:
        size = 20
    score += size * 0.20

    familiarity = 100 if person_used_product else 30
    score += familiarity * 0.15

    if company_raised_recently:
        budget = 100
    elif headcount_growing:
        budget = 60
    else:
        budget = 20
    score += budget * 0.10

    final = round(score)
    logger.debug(
        "calculate_score | title=%s seniority=%d(x0.30) | days=%d recency=%d(x0.25) | "
        "headcount=%s size=%d(x0.20) | familiarity=%d(x0.15) | budget=%d(x0.10) => %d",
        title, seniority, days_since_transition, recency,
        target_company_size, size, familiarity, budget, final,
    )
    return final


def calculate_urgency(score: int, days: int) -> str:
    if score >= 80 and days < 30:
        urgency = "hot"
    elif score >= 50 or days < 60:
        urgency = "warm"
    else:
        urgency = "cool"
    logger.debug("calculate_urgency | score=%d, days=%d => %s", score, days, urgency)
    return urgency


def days_since(date: datetime | None) -> int:
    if not date:
        return 999
    now = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return (now - date).days
