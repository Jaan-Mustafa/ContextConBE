import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Customer, TrackedPerson, Signal
from app.services.crustdata import crustdata_client
from app.services.signal_scorer import calculate_score, calculate_urgency, days_since

logger = logging.getLogger(__name__)


def _extract_people_from_response(data: dict) -> list[dict]:
    profiles = data.get("profiles", [])
    if not profiles:
        profiles = data if isinstance(data, list) else []
    return profiles


def _parse_person(profile: dict) -> dict:
    basic = profile.get("basic_profile", {})
    social = profile.get("social_handles", {})
    experience = profile.get("experience", {})
    employment = experience.get("employment_details", {})
    current_jobs = employment.get("current", [])
    past_jobs = employment.get("past", [])

    linkedin_url = social.get("professional_network_identifier", {}).get("profile_url", "")

    current_company = None
    current_title = basic.get("current_title", "")
    start_date = None
    if current_jobs:
        current_company = current_jobs[0].get("name")
        current_title = current_jobs[0].get("title", current_title)
        start_date = current_jobs[0].get("start_date")

    previous_company = None
    if past_jobs:
        previous_company = past_jobs[0].get("name")

    return {
        "crustdata_person_id": str(profile.get("crustdata_person_id", "")),
        "name": basic.get("name", "Unknown"),
        "title": current_title,
        "linkedin_url": linkedin_url,
        "current_company": current_company,
        "previous_company": previous_company,
        "start_date": start_date,
    }


async def scan_customers(
    db: AsyncSession,
    user_id: uuid.UUID,
    customers: list[Customer],
    product_name: str,
    product_description: str,
) -> dict:
    logger.info("======== scan_customers START | %d customers, product=%s ========",
                len(customers), product_name)
    all_signals = []
    people_tracked = 0

    for customer in customers:
        logger.info("-------- Scanning customer: %s (find who left) --------", customer.company_name)
        try:
            data = await crustdata_client.search_people(
                company_name=customer.company_name,
                seniority_levels=["CXO", "VP", "Director"],
            )
        except Exception as exc:
            logger.error("Failed to search people for customer %s: %s", customer.company_name, exc)
            continue

        profiles = _extract_people_from_response(data)
        logger.info("Customer %s: found %d people who left", customer.company_name, len(profiles))

        for profile in profiles:
            person_data = _parse_person(profile)
            people_tracked += 1

            current_company = person_data["current_company"]
            if not current_company:
                continue

            transition_date = None
            if person_data["start_date"]:
                try:
                    transition_date = datetime.fromisoformat(person_data["start_date"])
                except (ValueError, TypeError):
                    pass

            logger.info("DEPARTED: %s (%s) left %s -> %s",
                        person_data["name"], person_data["title"],
                        customer.company_name, current_company)

            tracked = TrackedPerson(
                crustdata_person_id=person_data["crustdata_person_id"],
                name=person_data["name"],
                title=person_data["title"],
                linkedin_url=person_data["linkedin_url"],
                current_company=current_company,
                previous_company=customer.company_name,
                transition_date=transition_date,
                status="departed",
                source="customer",
                source_id=customer.id,
            )
            db.add(tracked)
            await db.flush()

            days = days_since(transition_date)

            reasoning = (
                f"{person_data['name']} ({person_data['title']}) left {customer.company_name} "
                f"and joined {current_company}. They previously used {product_name} — "
                f"warm lead to bring {product_name} into {current_company}."
            )
            suggested_action = (
                f"Reach out to {person_data['name']} at {current_company}. "
                f"They already know {product_name} from {customer.company_name}."
            )

            score = calculate_score(
                title=person_data["title"],
                days_since_transition=days,
                target_company_size=None,
                person_used_product=True,
            )
            urgency = calculate_urgency(score, days)

            new_lead = Signal(
                user_id=user_id,
                person_id=tracked.id,
                type="new_lead",
                flow="champion_tracker",
                score=score,
                urgency=urgency,
                reasoning=reasoning,
                suggested_action=suggested_action,
                target_company=current_company,
            )
            db.add(new_lead)
            all_signals.append(new_lead)

            churn_reasoning = (
                f"Your champion {person_data['name']} ({person_data['title']}) "
                f"has left {customer.company_name}. This account may be at risk — "
                f"identify the new decision-maker."
            )
            churn_action = (
                f"Find who replaced {person_data['name']} at {customer.company_name} "
                f"and build a relationship with them to protect the account."
            )

            churn_score = calculate_score(
                title=person_data["title"],
                days_since_transition=days,
                target_company_size=customer.headcount,
                person_used_product=True,
            )
            churn_urgency = calculate_urgency(churn_score, days)

            churn_risk = Signal(
                user_id=user_id,
                person_id=tracked.id,
                type="churn_risk",
                flow="champion_tracker",
                score=churn_score,
                urgency=churn_urgency,
                reasoning=churn_reasoning,
                suggested_action=churn_action,
                target_company=customer.company_name,
                target_company_size=customer.headcount,
                target_company_revenue_lower=customer.revenue_lower,
                target_company_revenue_upper=customer.revenue_upper,
            )
            db.add(churn_risk)
            all_signals.append(churn_risk)

        logger.info("Customer %s: %d signals generated so far",
                    customer.company_name, len(all_signals))

    await db.flush()

    logger.info("======== scan_customers DONE | tracked=%d, signals=%d ========",
                people_tracked, len(all_signals))
    return {
        "people_tracked": people_tracked,
        "signals": all_signals,
    }
