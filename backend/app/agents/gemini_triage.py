"""
GeminiTriageAgent — Enhanced triage using Google Gemini 1.5 Flash.

Falls back gracefully to the rule-based TriageAgent when:
  - GEMINI_API_KEY is not set
  - The Gemini API call fails for any reason
  - The response cannot be parsed as valid JSON

Usage: import SmartTriageAgent instead of TriageAgent in pipeline.py
"""
import json
import hashlib
import logging
from datetime import datetime

from app.core.config import settings
from app.models.db_models import Emergency, AgentLog, SeverityLevel
from app.agents.triage_agent import TriageAgent
from app.database import AsyncSession

logger = logging.getLogger(__name__)


GEMINI_SYSTEM_PROMPT = """You are an expert emergency medical triage AI for Nepal's emergency response system (RapidAid.ai).

Your job: Analyze an emergency description and return a structured JSON triage decision.

Severity levels:
- P1_CRITICAL: Immediate life threat (cardiac arrest, no pulse, not breathing, stroke, severe hemorrhage, drowning, overdose)
- P2_URGENT: Serious but not immediately fatal (fractures, head injury, difficulty breathing, burns, high fever, labor)
- P3_MODERATE: Requires medical attention (moderate bleeding, pain, dizziness, nausea, sprains)
- P4_MINOR: Non-urgent (minor cuts, mild pain, routine transport)

Medical categories: CARDIAC, STROKE, TRAUMA, RESPIRATORY, MATERNITY, BURN, GENERAL

Return ONLY valid JSON (no markdown, no explanation) in exactly this format:
{
  "severity": "P1_CRITICAL",
  "medical_category": "CARDIAC",
  "confidence": 0.95,
  "reasoning": "Patient described as unconscious with no pulse — classic cardiac arrest indicators. Immediate P1_CRITICAL.",
  "key_indicators": ["unconscious", "no pulse"],
  "recommended_specialization": "CARDIAC"
}

Be conservative: when uncertain, escalate severity. Time = lives in Kathmandu traffic."""


SEVERITY_MAP = {
    "P1_CRITICAL": SeverityLevel.P1_CRITICAL,
    "P2_URGENT": SeverityLevel.P2_URGENT,
    "P3_MODERATE": SeverityLevel.P3_MODERATE,
    "P4_MINOR": SeverityLevel.P4_MINOR,
}

VALID_CATEGORIES = {"CARDIAC", "STROKE", "TRAUMA", "RESPIRATORY", "MATERNITY", "BURN", "GENERAL"}


class GeminiTriageAgent:
    """
    Triage agent powered by Google Gemini 1.5 Flash.
    Raises RuntimeError if Gemini is unavailable — caller should catch and fallback.
    """

    def __init__(self):
        self._client = None
        self._available = False
        self._model_name = "gemini-1.5-flash"

        if not settings.GEMINI_API_KEY:
            logger.info("GeminiTriageAgent: GEMINI_API_KEY not set — agent disabled")
            return

        try:
            import google.generativeai as genai  # type: ignore
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._client = genai.GenerativeModel(
                model_name=self._model_name,
                system_instruction=GEMINI_SYSTEM_PROMPT,
                generation_config={
                    "temperature": 0.1,      # Low temp for consistent medical decisions
                    "top_p": 0.95,
                    "max_output_tokens": 512,
                    "response_mime_type": "application/json",
                },
            )
            self._available = True
            logger.info("GeminiTriageAgent: Initialized with model %s", self._model_name)
        except ImportError:
            logger.warning("GeminiTriageAgent: google-generativeai not installed — disabled")
        except Exception as exc:
            logger.error("GeminiTriageAgent: Initialization failed: %s", exc)

    @property
    def is_available(self) -> bool:
        return self._available

    async def triage(self, description: str) -> dict:
        """
        Call Gemini and return parsed triage decision dict.
        Raises RuntimeError on any failure so SmartTriageAgent can fallback.
        """
        if not self._available or not self._client:
            raise RuntimeError("Gemini not available")

        try:
            # Build user message
            user_message = f"Emergency description: {description or 'No description provided'}"

            # Run in executor to avoid blocking event loop (Gemini SDK is sync)
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._client.generate_content(user_message)
            )

            raw_text = response.text.strip()

            # Remove markdown code fences if model adds them despite mime type
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
                raw_text = raw_text.strip()

            result = json.loads(raw_text)

            # Validate required fields
            if "severity" not in result or "medical_category" not in result:
                raise ValueError("Gemini response missing required fields")

            # Validate enum values
            if result["severity"] not in SEVERITY_MAP:
                raise ValueError(f"Unknown severity: {result['severity']}")
            if result.get("medical_category", "GENERAL") not in VALID_CATEGORIES:
                result["medical_category"] = "GENERAL"

            return result

        except Exception as exc:
            logger.error("GeminiTriageAgent.triage() failed: %s", exc)
            raise RuntimeError(f"Gemini triage failed: {exc}") from exc


class SmartTriageAgent:
    """
    Wrapper that tries Gemini first, falls back to rule-based TriageAgent.
    Logs results as GEMINI_TRIAGE_AGENT or TRIAGE_AGENT in AgentLog.
    """

    def __init__(self):
        self._gemini = GeminiTriageAgent()
        self._rules = TriageAgent()

    async def process(self, emergency: Emergency, db: AsyncSession):
        """
        Try Gemini triage; fall back to rule-based triage on failure.
        Mutates emergency.severity, emergency.medical_category, emergency.ai_confidence_score.
        Creates AgentLog entry.
        """
        desc = emergency.description or ""

        # --- Attempt Gemini ---
        if self._gemini.is_available:
            try:
                result = await self._gemini.triage(desc)

                severity_enum = SEVERITY_MAP[result["severity"]]
                category = result.get("medical_category", "GENERAL")
                confidence = float(result.get("confidence", 0.90))
                reasoning = result.get("reasoning", "Gemini triage decision")
                key_indicators = result.get("key_indicators", [])

                emergency.severity = severity_enum
                emergency.medical_category = category
                emergency.ai_confidence_score = confidence

                decision_text = (
                    f"[GEMINI] Triaged as {severity_enum.value} | Category: {category} | "
                    f"Key indicators: {', '.join(key_indicators) if key_indicators else 'N/A'}"
                )

                log_hash = hashlib.sha256(
                    f"{emergency.id}-GEMINI-{datetime.utcnow().isoformat()}".encode()
                ).hexdigest()

                log = AgentLog(
                    emergency_id=emergency.id,
                    agent_name="GEMINI_TRIAGE_AGENT",
                    decision=decision_text,
                    reasoning=reasoning,
                    confidence=confidence,
                    decision_hash=log_hash,
                )
                db.add(log)
                await db.flush()
                logger.info("SmartTriageAgent: Gemini decision — %s / %s (conf=%.2f)", severity_enum.value, category, confidence)
                return  # Success — skip fallback

            except Exception as exc:
                logger.warning("SmartTriageAgent: Gemini failed (%s), falling back to rules", exc)

        # --- Fallback: Rule-based ---
        await self._rules.process(emergency, db)
        logger.info(
            "SmartTriageAgent: Rule-based decision — %s / %s",
            emergency.severity,
            emergency.medical_category,
        )
