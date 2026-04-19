import json
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

API_VERSION = "2025-11-01"


def _truncate(obj, max_len: int = 200) -> str:
    text = json.dumps(obj) if not isinstance(obj, str) else obj
    return text[:max_len] + "..." if len(text) > max_len else text


class CrustDataClient:
    def __init__(self):
        self.base_url = settings.crustdata_base_url
        self.headers = {
            "Authorization": f"Bearer {settings.crustdata_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-version": API_VERSION,
        }

    async def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        logger.info("CrustData POST %s | payload: %s", endpoint, _truncate(payload))
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, json=payload, headers=self.headers)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "CrustData POST %s -> %s (%d bytes, %.1fms)",
                    endpoint, resp.status_code, len(resp.content), elapsed_ms,
                )
                if resp.status_code >= 400:
                    logger.error("CrustData POST %s RESPONSE BODY: %s", endpoint, resp.text[:500])
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("CrustData POST %s FAILED after %.1fms: %s", endpoint, elapsed_ms, exc)
            raise

    async def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{self.base_url}{endpoint}"
        logger.info("CrustData GET %s | params: %s", endpoint, _truncate(params))
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers=self.headers)
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "CrustData GET %s -> %s (%d bytes, %.1fms)",
                    endpoint, resp.status_code, len(resp.content), elapsed_ms,
                )
                if resp.status_code >= 400:
                    logger.error("CrustData GET %s RESPONSE BODY: %s", endpoint, resp.text[:500])
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("CrustData GET %s FAILED after %.1fms: %s", endpoint, elapsed_ms, exc)
            raise

    async def search_people(
        self,
        company_name: str,
        seniority_levels: list[str] | None = None,
        recently_changed_jobs: bool = False,
        page: int = 1,
    ) -> dict:
        """Search people whose PAST company matches — i.e. people who LEFT this company."""
        if seniority_levels is None:
            seniority_levels = ["CXO", "VP", "Director"]

        conditions = [
            {
                "field": "experience.employment_details.past.company_name",
                "type": "(.)",
                "value": company_name,
            },
            {
                "field": "experience.employment_details.current.seniority_level",
                "type": "in",
                "value": seniority_levels,
            },
        ]

        if recently_changed_jobs:
            conditions.append({
                "field": "recently_changed_jobs",
                "type": "=",
                "value": True,
            })

        payload = {
            "filters": {"op": "and", "conditions": conditions},
            "limit": 25,
        }
        logger.info("search_people(past_company=%s, seniority=%s, changed_jobs=%s)",
                     company_name, seniority_levels, recently_changed_jobs)
        return await self._post("/person/search", payload)

    async def search_people_at_company(
        self,
        company_name: str,
        seniority_levels: list[str] | None = None,
    ) -> dict:
        """Search people currently at a company."""
        if seniority_levels is None:
            seniority_levels = ["CXO", "VP", "Director"]

        conditions = [
            {
                "field": "experience.employment_details.current.company_name",
                "type": "(.)",
                "value": company_name,
            },
            {
                "field": "experience.employment_details.current.seniority_level",
                "type": "in",
                "value": seniority_levels,
            },
        ]

        payload = {
            "filters": {"op": "and", "conditions": conditions},
            "limit": 25,
        }
        logger.info("search_people_at_company(company=%s, seniority=%s)",
                     company_name, seniority_levels)
        return await self._post("/person/search", payload)

    async def search_company(self, domain: str) -> dict:
        """Search company by domain."""
        payload = {
            "filters": {
                "field": "basic_info.primary_domain",
                "type": "=",
                "value": domain,
            },
            "fields": [
                "basic_info",
                "headcount",
                "funding",
                "revenue",
            ],
            "limit": 1,
        }
        logger.info("search_company(domain=%s)", domain)
        return await self._post("/company/search", payload)

    async def search_company_by_name(self, name: str) -> dict:
        """Search company by name."""
        payload = {
            "filters": {
                "field": "basic_info.name",
                "type": "(.)",
                "value": name,
            },
            "fields": [
                "basic_info",
                "headcount",
                "funding",
                "revenue",
            ],
            "limit": 5,
        }
        logger.info("search_company_by_name(name=%s)", name)
        return await self._post("/company/search", payload)


crustdata_client = CrustDataClient()
