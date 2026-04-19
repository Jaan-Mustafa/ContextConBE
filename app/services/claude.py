import json
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _trunc(text: str, max_len: int = 200) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


class ClaudeClient:
    def __init__(self):
        self.base_url = settings.llm_base_url
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model

    async def _ask(self, system: str, user_message: str) -> str:
        logger.info("LLM _ask | system: %s", _trunc(system, 120))
        logger.info("LLM _ask | user_message: %s", _trunc(user_message))
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 1024,
        }

        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info("LLM _ask -> OK (%.1fms, %d chars) | response: %s",
                            elapsed_ms, len(content), _trunc(content))
                return content
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error("LLM _ask FAILED after %.1fms: %s", elapsed_ms, exc)
            raise

    async def extract_tech_stack(self, job_descriptions: list[str]) -> list[dict]:
        logger.info("extract_tech_stack | %d job descriptions", len(job_descriptions))
        system = (
            "You are a tech stack extraction engine. Given job descriptions, "
            "extract all tools, platforms, and vendor products mentioned. "
            "Return a JSON array of objects with 'name' and 'category' fields. "
            "Categories: observability, database, cloud, ci_cd, messaging, analytics, "
            "security, devops, frontend, backend, ml, other. "
            "Only return the JSON array, no other text."
        )

        combined = "\n---\n".join(job_descriptions[:10])
        user_msg = f"Extract the tech stack from these job descriptions:\n\n{combined}"

        result = await self._ask(system, user_msg)
        try:
            parsed = json.loads(result)
            logger.info("extract_tech_stack -> %d items extracted", len(parsed))
            return parsed
        except json.JSONDecodeError:
            logger.warning("extract_tech_stack -> JSON parse failed, returning empty list")
            return []

    async def analyze_opportunity(
        self,
        person_name: str,
        person_title: str,
        previous_company: str,
        new_company: str,
        product_name: str,
        product_description: str,
    ) -> dict:
        logger.info("analyze_opportunity | person=%s, %s -> %s, product=%s",
                     person_name, previous_company, new_company, product_name)
        system = (
            "You are a sales intelligence analyst. Analyze a leadership transition "
            "and explain why this is a sales opportunity. Be specific and actionable. "
            "Return JSON with 'reasoning' and 'suggested_action' fields. Only return valid JSON."
        )

        user_msg = (
            f"Person: {person_name} ({person_title})\n"
            f"Left: {previous_company}\n"
            f"Joined: {new_company}\n"
            f"Our product: {product_name} - {product_description}\n"
            f"They used our product at {previous_company}.\n\n"
            f"Why is this a sales opportunity at {new_company}? "
            f"What should the sales team do?"
        )

        result = await self._ask(system, user_msg)
        try:
            parsed = json.loads(result)
            logger.info("analyze_opportunity -> OK | reasoning: %s", _trunc(parsed.get("reasoning", ""), 120))
            return parsed
        except json.JSONDecodeError:
            logger.warning("analyze_opportunity -> JSON parse failed, using raw text as reasoning")
            return {
                "reasoning": result,
                "suggested_action": f"Reach out to {person_name} at {new_company} about {product_name}.",
            }

    async def analyze_churn_risk(
        self,
        person_name: str,
        person_title: str,
        customer_company: str,
        product_name: str,
    ) -> dict:
        logger.info("analyze_churn_risk | person=%s left %s, product=%s",
                     person_name, customer_company, product_name)
        system = (
            "You are a customer success analyst. A key champion has left a customer company. "
            "Analyze the churn risk and suggest retention actions. "
            "Return JSON with 'reasoning' and 'suggested_action' fields. Only return valid JSON."
        )

        user_msg = (
            f"Champion: {person_name} ({person_title}) has LEFT {customer_company}.\n"
            f"They were the internal champion for our product: {product_name}.\n\n"
            f"What is the churn risk? What should we do to retain this account?"
        )

        result = await self._ask(system, user_msg)
        try:
            parsed = json.loads(result)
            logger.info("analyze_churn_risk -> OK | reasoning: %s", _trunc(parsed.get("reasoning", ""), 120))
            return parsed
        except json.JSONDecodeError:
            logger.warning("analyze_churn_risk -> JSON parse failed, using raw text")
            return {
                "reasoning": result,
                "suggested_action": f"Identify the new decision-maker at {customer_company} and engage immediately.",
            }

    async def analyze_displacement(
        self,
        person_name: str,
        person_title: str,
        target_company: str,
        our_product: str,
        competitor_product: str,
    ) -> dict:
        logger.info("analyze_displacement | person=%s, target=%s, ours=%s vs competitor=%s",
                     person_name, target_company, our_product, competitor_product)
        system = (
            "You are a competitive intelligence analyst. A new leader joined a company "
            "that uses a competitor's product, but this leader previously used OUR product. "
            "Analyze the displacement opportunity. "
            "Return JSON with 'reasoning' and 'suggested_action' fields. Only return valid JSON."
        )

        user_msg = (
            f"Person: {person_name} ({person_title})\n"
            f"Joined: {target_company} (currently uses {competitor_product})\n"
            f"Previously used: {our_product} at their old company\n\n"
            f"What's the competitive displacement opportunity?"
        )

        result = await self._ask(system, user_msg)
        try:
            parsed = json.loads(result)
            logger.info("analyze_displacement -> OK | reasoning: %s", _trunc(parsed.get("reasoning", ""), 120))
            return parsed
        except json.JSONDecodeError:
            logger.warning("analyze_displacement -> JSON parse failed, using raw text")
            return {
                "reasoning": result,
                "suggested_action": f"Reach out to {person_name} — they know {our_product} and may replace {competitor_product}.",
            }

    async def generate_outreach(
        self,
        person_name: str,
        person_title: str,
        previous_company: str,
        new_company: str,
        signal_type: str,
        product_name: str,
        product_description: str,
        reasoning: str,
    ) -> dict:
        logger.info("generate_outreach | person=%s, signal_type=%s, %s -> %s",
                     person_name, signal_type, previous_company, new_company)
        tone_map = {
            "new_lead": "warm_reconnect",
            "churn_risk": "retention_save",
            "competitive_displacement": "competitive_pitch",
        }
        tone = tone_map.get(signal_type, "warm_reconnect")

        system = (
            "You are an expert sales copywriter. Write a personalized outreach email "
            "that feels genuine, not salesy. Reference specific details about the person's "
            "background. Keep the email under 150 words. "
            "Return JSON with fields: 'subject_line', 'email_body', "
            "'talking_points' (array of strings), 'timing_recommendation'. Only return valid JSON."
        )

        user_msg = (
            f"Signal type: {signal_type}\n"
            f"Tone: {tone}\n"
            f"Person: {person_name} ({person_title})\n"
            f"Previous company: {previous_company}\n"
            f"Current company: {new_company}\n"
            f"Our product: {product_name} - {product_description}\n"
            f"Context: {reasoning}\n\n"
            f"Write the outreach email."
        )

        result = await self._ask(system, user_msg)
        try:
            data = json.loads(result)
            data["tone"] = tone
            logger.info("generate_outreach -> OK | subject: %s", _trunc(data.get("subject_line", ""), 120))
            return data
        except json.JSONDecodeError:
            logger.warning("generate_outreach -> JSON parse failed, using raw text as email_body")
            return {
                "subject_line": f"Congrats on the new role at {new_company}, {person_name}!",
                "email_body": result,
                "talking_points": [reasoning],
                "tone": tone,
                "timing_recommendation": "Send within 7 days",
            }

    async def validate_competitor_customers(
        self,
        job_descriptions: list[dict],
        competitor_product: str,
    ) -> list[dict]:
        logger.info("validate_competitor_customers | %d jobs, product=%s",
                     len(job_descriptions), competitor_product)
        system = (
            "You are analyzing job descriptions to identify which companies use a specific product. "
            "For each company, assess confidence (0-1) that they are an actual user of the product "
            "(not just mentioning it casually). "
            "Return a JSON array of objects with 'company_name' and 'confidence' fields. "
            "Only include companies with confidence > 0.5. Only return valid JSON."
        )

        descriptions = []
        for job in job_descriptions[:20]:
            company = job.get("company", {}).get("basic_info", {}).get("name", "Unknown")
            desc = job.get("content", {}).get("description", "")[:500]
            descriptions.append(f"Company: {company}\nJob: {desc}")

        user_msg = (
            f"Product to check for: {competitor_product}\n\n"
            f"Job descriptions:\n\n" + "\n---\n".join(descriptions)
        )

        result = await self._ask(system, user_msg)
        try:
            parsed = json.loads(result)
            logger.info("validate_competitor_customers -> %d companies validated", len(parsed))
            return parsed
        except json.JSONDecodeError:
            logger.warning("validate_competitor_customers -> JSON parse failed, returning empty list")
            return []


claude_client = ClaudeClient()
