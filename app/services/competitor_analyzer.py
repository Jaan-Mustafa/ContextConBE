import logging
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Competitor, CompetitorCustomer, TrackedPerson, Signal
from app.services.crustdata import crustdata_client
from app.services.signal_scorer import calculate_score, calculate_urgency, days_since
from app.services.champion_tracker import _extract_people_from_response, _parse_person

logger = logging.getLogger(__name__)


async def discover_competitor_customers(
    db: AsyncSession,
    competitor: Competitor,
) -> list[CompetitorCustomer]:
    logger.info("-------- discover_competitor_customers: %s --------", competitor.company_name)
    discovered = []

    try:
        data = await crustdata_client.search_people_at_company(
            company_name=competitor.company_name,
            seniority_levels=["CXO", "VP", "Director"],
        )
    except Exception as exc:
        logger.error("Failed to search people for competitor %s: %s", competitor.company_name, exc)
        return discovered

    profiles = _extract_people_from_response(data)

    company_names = set()
    for profile in profiles:
        person_data = _parse_person(profile)
        if person_data["previous_company"]:
            company_names.add(person_data["previous_company"])

    for company_name in company_names:
        comp_customer = CompetitorCustomer(
            competitor_id=competitor.id,
            company_name=company_name,
            discovered_via="people_movement",
            confidence=0.6,
        )
        db.add(comp_customer)
        discovered.append(comp_customer)

    await db.flush()
    logger.info("Competitor %s: discovered %d potential customers", competitor.company_name, len(discovered))
    return discovered


async def scan_competitor_customers(
    db: AsyncSession,
    user_id: uuid.UUID,
    competitors: list[Competitor],
    product_name: str,
    product_description: str,
) -> dict:
    logger.info("======== scan_competitor_customers START | %d competitors, product=%s ========",
                len(competitors), product_name)
    all_signals = []
    total_discovered = 0
    people_tracked = 0

    for competitor in competitors:
        logger.info("-------- Analyzing competitor: %s (product: %s) --------",
                    competitor.company_name, competitor.product_name)
        comp_customers = await discover_competitor_customers(db, competitor)
        total_discovered += len(comp_customers)

        for comp_customer in comp_customers:
            try:
                data = await crustdata_client.search_people(
                    company_name=comp_customer.company_name,
                    seniority_levels=["CXO", "VP", "Director"],
                    recently_changed_jobs=True,
                )
            except Exception as exc:
                logger.error("Failed to search people for competitor customer %s: %s",
                             comp_customer.company_name, exc)
                continue

            profiles = _extract_people_from_response(data)

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

                tracked = TrackedPerson(
                    crustdata_person_id=person_data["crustdata_person_id"],
                    name=person_data["name"],
                    title=person_data["title"],
                    linkedin_url=person_data["linkedin_url"],
                    current_company=current_company,
                    previous_company=comp_customer.company_name,
                    transition_date=transition_date,
                    status="departed",
                    source="competitor_customer",
                    source_id=comp_customer.id,
                )
                db.add(tracked)
                await db.flush()

                days = days_since(transition_date)

                logger.info("Displacement: %s (%s) left %s -> %s (competitor customer of %s)",
                            person_data["name"], person_data["title"],
                            comp_customer.company_name, current_company, competitor.company_name)

                reasoning = (
                    f"{person_data['name']} ({person_data['title']}) left {comp_customer.company_name} "
                    f"(a {competitor.product_name} customer) and joined {current_company}. "
                    f"Opportunity to displace {competitor.product_name} with {product_name}."
                )
                suggested_action = (
                    f"Reach out to {person_data['name']} at {current_company}. "
                    f"They know {competitor.product_name} — pitch {product_name} as a better alternative."
                )

                score = calculate_score(
                    title=person_data["title"],
                    days_since_transition=days,
                    target_company_size=None,
                    person_used_product=True,
                )
                urgency = calculate_urgency(score, days)

                signal = Signal(
                    user_id=user_id,
                    person_id=tracked.id,
                    type="competitive_displacement",
                    flow="competitor_analyzer",
                    score=score,
                    urgency=urgency,
                    reasoning=reasoning,
                    suggested_action=suggested_action,
                    target_company=comp_customer.company_name,
                )
                db.add(signal)
                all_signals.append(signal)

    await db.flush()

    logger.info("======== scan_competitor_customers DONE | tracked=%d, discovered=%d, signals=%d ========",
                people_tracked, total_discovered, len(all_signals))
    return {
        "people_tracked": people_tracked,
        "competitor_customers_discovered": total_discovered,
        "signals": all_signals,
    }
