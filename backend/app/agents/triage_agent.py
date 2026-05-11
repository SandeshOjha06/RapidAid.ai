"""
TriageAgent — Rule-based emergency triage.

Used directly when Gemini is unavailable, and as fallback inside SmartTriageAgent.

Triage logic:
  1. Keyword scan on description text
  2. Medical category detection
  3. Category severity floor (e.g., CARDIAC always at least P1_CRITICAL)
  4. Take the most severe result
"""
import hashlib
import logging
from datetime import datetime

from app.models.db_models import SeverityLevel, Emergency, AgentLog
from app.database import AsyncSession

logger = logging.getLogger(__name__)


# ─────────────────────────── Keyword Tables ──────────────────────────────────

CRITICAL_KEYWORDS = [
    # English
    "unconscious", "not breathing", "no pulse", "cardiac arrest",
    "heart attack", "stroke", "severe bleeding", "unresponsive",
    "choking", "drowning", "electrocuted", "not responding",
    "stopped breathing", "blue lips", "collapsed", "overdose",
    "chest pain", "anaphylaxis", "anaphylactic shock", "arterial bleeding",
    # Nepali (romanized)
    "hosh chaina", "sas chaina", "pulse chaina", "behos",
    "dhadkan banda", "khun aairako",
]

URGENT_KEYWORDS = [
    # English
    "difficulty breathing", "shortness of breath", "broken bone", "fracture",
    "head injury", "pregnancy", "labor", "seizure", "high fever",
    "vomiting blood", "allergic reaction", "burns", "accident",
    "crash", "hit by vehicle", "fall from height", "diabetic emergency",
    "loss of consciousness", "unconscious briefly",
    # Nepali (romanized)
    "sas lina garo", "haddi bhachyo", "dudh chhenchi", "dubyo",
    "jal bhayo", "accident bhayo",
]

MODERATE_KEYWORDS = [
    # English
    "bleeding", "pain", "injured", "fell", "cut", "bite", "sprain",
    "nausea", "dizziness", "weakness", "headache", "abdominal pain", "back pain",
    "vomiting", "diarrhea", "mild fever", "swelling",
    # Nepali (romanized)
    "khun aayo", "dukeko", "jharna bhayo", "roga layo",
]


# ─────────────────────────── Category Map ────────────────────────────────────
# ORDER MATTERS: More specific categories first.
# STROKE must appear before CARDIAC because stroke may mention chest-adjacent terms.

CATEGORY_MAP = [
    # (category_name, [keywords])
    ("STROKE",      ["stroke", "face drooping", "facial droop", "arm weakness",
                     "speech difficulty", "speech slurred", "sudden numbness", "numb face",
                     "vision loss suddenly", "severe headache sudden"]),
    ("CARDIAC",     ["heart", "cardiac", "chest pain", "heart attack", "palpitation",
                     "chest tightness", "chest pressure", "myocardial"]),
    ("MATERNITY",   ["pregnancy", "labor", "contractions", "delivery", "pregnant",
                     "birth", "miscarriage", "water broke", "prenatal"]),
    ("BURN",        ["burn", "fire", "scalded", "smoke inhalation", "chemical burn"]),
    ("TRAUMA",      ["accident", "crash", "fall", "fracture", "broken", "hit by",
                     "collision", "stabbed", "gunshot", "cut deep", "amputation"]),
    ("RESPIRATORY", ["breathing", "breath", "asthma", "choke", "oxygen", "lungs",
                     "inhaled", "shortness of breath", "difficulty breathing", "coughing blood"]),
    ("GENERAL",     []),  # Catch-all — always matches
]

# Minimum severity per category
TYPE_SEVERITY_FLOOR = {
    "CARDIAC":     SeverityLevel.P1_CRITICAL,
    "STROKE":      SeverityLevel.P1_CRITICAL,
    "TRAUMA":      SeverityLevel.P2_URGENT,
    "RESPIRATORY": SeverityLevel.P2_URGENT,
    "BURN":        SeverityLevel.P2_URGENT,
    "MATERNITY":   SeverityLevel.P2_URGENT,
    "GENERAL":     SeverityLevel.P3_MODERATE,
}

SEVERITY_RANK = {
    SeverityLevel.P1_CRITICAL: 1,
    SeverityLevel.P2_URGENT:   2,
    SeverityLevel.P3_MODERATE: 3,
    SeverityLevel.P4_MINOR:    4,
}


# ─────────────────────────── Agent ───────────────────────────────────────────

class TriageAgent:
    """Rule-based triage agent. Works entirely offline with zero API calls."""

    async def process(self, emergency: Emergency, db: AsyncSession):
        desc = (emergency.description or "").lower()

        # 1. Keyword severity scan
        if any(k in desc for k in CRITICAL_KEYWORDS):
            detected_severity = SeverityLevel.P1_CRITICAL
        elif any(k in desc for k in URGENT_KEYWORDS):
            detected_severity = SeverityLevel.P2_URGENT
        elif any(k in desc for k in MODERATE_KEYWORDS):
            detected_severity = SeverityLevel.P3_MODERATE
        else:
            detected_severity = SeverityLevel.P4_MINOR

        # 2. Category detection — ordered list, first match wins
        detected_category = "GENERAL"
        matched_keywords = []
        for cat, keywords in CATEGORY_MAP:
            hits = [k for k in keywords if k and k in desc]
            if hits:
                detected_category = cat
                matched_keywords = hits
                break

        # 3. Category severity floor
        floor_severity = TYPE_SEVERITY_FLOOR.get(detected_category, SeverityLevel.P4_MINOR)

        # 4. Take the most critical (lowest rank number)
        if SEVERITY_RANK[floor_severity] < SEVERITY_RANK[detected_severity]:
            final_severity = floor_severity
            severity_source = f"category floor ({detected_category})"
        else:
            final_severity = detected_severity
            severity_source = "keyword scan"

        emergency.severity = final_severity
        emergency.medical_category = detected_category

        # Confidence: higher for clearer signals
        confidence = {
            SeverityLevel.P1_CRITICAL: 0.92,
            SeverityLevel.P2_URGENT:   0.85,
            SeverityLevel.P3_MODERATE: 0.75,
            SeverityLevel.P4_MINOR:    0.65,
        }.get(final_severity, 0.70)
        emergency.ai_confidence_score = confidence

        decision_text = f"[RULES] Triaged as {final_severity.value} | Category: {detected_category}"
        reasoning = (
            f"Keyword scan on: '{desc[:200]}...'. "
            f"Detected severity: {detected_severity.value} (from {severity_source}). "
            f"Category: {detected_category} (matched: {matched_keywords}). "
            f"Floor: {floor_severity.value}. Final: {final_severity.value}."
        )

        log = AgentLog(
            emergency_id=emergency.id,
            agent_name="TRIAGE_AGENT",
            decision=decision_text,
            reasoning=reasoning,
            confidence=confidence,
            decision_hash=hashlib.sha256(
                f"{emergency.id}-TRIAGE-{datetime.utcnow().isoformat()}".encode()
            ).hexdigest(),
        )
        db.add(log)
        await db.flush()
        logger.info(
            "TriageAgent → %s / %s (conf=%.2f, source=%s)",
            final_severity.value, detected_category, confidence, severity_source
        )
