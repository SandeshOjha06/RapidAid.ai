"""
SmartTriageAgent — Enhanced triage using LLaMA 3.3 via Groq.

Falls back gracefully to the rule-based TriageAgent when:
  - GROQ_API_KEY is not set
  - The Groq API call fails for any reason
  - The response cannot be parsed as valid JSON

Usage: import SmartTriageAgent instead of TriageAgent in pipeline.py
"""
import hashlib
import logging
from datetime import datetime

from app.models.db_models import Emergency, AgentLog, SeverityLevel
from app.agents.triage_agent import TriageAgent
from app.agents.groq_client import groq_client
from app.database import AsyncSession

logger = logging.getLogger(__name__)

LLM_SYSTEM_PROMPT = """You are an expert emergency medical triage AI for Nepal's emergency response system (RapidAid.ai).

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

class SmartTriageAgent:
    """
    Wrapper that tries Groq LLM first, falls back to rule-based TriageAgent.
    Logs results as LLM_TRIAGE_AGENT or TRIAGE_AGENT in AgentLog.
    """

    def __init__(self):
        self._rules = TriageAgent()

    async def process(self, emergency: Emergency, db: AsyncSession):
        """
        Try LLM triage; fall back to rule-based triage on failure.
        Mutates emergency.severity, emergency.medical_category, emergency.ai_confidence_score.
        Creates AgentLog entry.
        """
        desc = emergency.description or ""

        # --- Attempt Groq LLM ---
        if groq_client.is_available:
            try:
                user_message = f"Emergency description: {desc or 'No description provided'}"
                
                response_text = await groq_client.chat(
                    system_prompt=LLM_SYSTEM_PROMPT,
                    user_message=user_message,
                    temperature=0.1
                )
                
                if not response_text:
                    raise RuntimeError("No response from Groq")
                
                result = groq_client.extract_json(response_text)
                if not result:
                    raise RuntimeError("Failed to parse JSON from Groq response")

                # Validate required fields
                if "severity" not in result or "medical_category" not in result:
                    raise ValueError("Groq response missing required fields")

                # Validate enum values
                if result["severity"] not in SEVERITY_MAP:
                    raise ValueError(f"Unknown severity: {result['severity']}")
                if result.get("medical_category", "GENERAL") not in VALID_CATEGORIES:
                    result["medical_category"] = "GENERAL"

                severity_enum = SEVERITY_MAP[result["severity"]]
                category = result.get("medical_category", "GENERAL")
                confidence = float(result.get("confidence", 0.90))
                reasoning = result.get("reasoning", "LLM triage decision")
                key_indicators = result.get("key_indicators", [])

                emergency.severity = severity_enum
                emergency.medical_category = category
                emergency.ai_confidence_score = confidence

                decision_text = (
                    f"[LLM] Triaged as {severity_enum.value} | Category: {category} | "
                    f"Key indicators: {', '.join(key_indicators) if key_indicators else 'N/A'}"
                )

                log_hash = hashlib.sha256(
                    f"{emergency.id}-LLM-{datetime.utcnow().isoformat()}".encode()
                ).hexdigest()

                log = AgentLog(
                    emergency_id=emergency.id,
                    agent_name="LLM_TRIAGE_AGENT",
                    decision=decision_text,
                    reasoning=reasoning,
                    confidence=confidence,
                    decision_hash=log_hash,
                )
                db.add(log)
                await db.flush()
                logger.info("SmartTriageAgent: LLM decision — %s / %s (conf=%.2f)", severity_enum.value, category, confidence)
                return  # Success — skip fallback

            except Exception as exc:
                logger.warning("SmartTriageAgent: LLM failed (%s), falling back to rules", exc)

        # --- Fallback: Rule-based ---
        await self._rules.process(emergency, db)
        logger.info(
            "SmartTriageAgent: Rule-based decision — %s / %s",
            emergency.severity,
            emergency.medical_category,
        )
