import hashlib
import json
from datetime import datetime
from app.models.db_models import SeverityLevel, Emergency, AgentLog
from app.database import AsyncSession

CRITICAL_KEYWORDS = [
    "unconscious", "not breathing", "no pulse", "cardiac arrest",
    "heart attack", "stroke", "severe bleeding", "unresponsive",
    "choking", "drowning", "electrocuted", "not responding",
    "stopped breathing", "blue lips", "collapsed", "overdose",
    "chest pain"
]

URGENT_KEYWORDS = [
    "difficulty breathing", "shortness of breath", "broken bone", "fracture",
    "head injury", "pregnancy", "labor", "seizure", "high fever",
    "vomiting blood", "allergic reaction", "burns", "accident",
    "crash", "hit by vehicle", "fall from height"
]

MODERATE_KEYWORDS = [
    "bleeding", "pain", "injured", "fell", "cut", "bite", "sprain",
    "nausea", "dizziness", "weakness", "headache", "abdominal pain", "back pain"
]

CATEGORY_MAP = {
    "CARDIAC":     ["heart", "cardiac", "chest pain", "heart attack", "palpitation"],
    "TRAUMA":      ["accident", "crash", "fall", "fracture", "broken", "hit", "collision"],
    "STROKE":      ["stroke", "face drooping", "arm weakness", "speech difficulty", "numb"],
    "RESPIRATORY": ["breathing", "breath", "asthma", "choke", "oxygen", "lungs"],
    "MATERNITY":   ["pregnancy", "labor", "contractions", "delivery", "pregnant", "birth"],
    "BURN":        ["burn", "fire", "scalded", "smoke"],
    "GENERAL":     [],
}

TYPE_SEVERITY_FLOOR = {
    "CARDIAC": SeverityLevel.P1_CRITICAL,
    "STROKE": SeverityLevel.P1_CRITICAL,
    "TRAUMA": SeverityLevel.P2_URGENT,
    "RESPIRATORY": SeverityLevel.P2_URGENT,
    "BURN": SeverityLevel.P2_URGENT,
    "MATERNITY": SeverityLevel.P2_URGENT,
    "GENERAL": SeverityLevel.P3_MODERATE,
}

SEVERITY_RANK = {
    SeverityLevel.P1_CRITICAL: 1,
    SeverityLevel.P2_URGENT: 2,
    SeverityLevel.P3_MODERATE: 3,
    SeverityLevel.P4_MINOR: 4
}

class TriageAgent:
    async def process(self, emergency: Emergency, db: AsyncSession):
        desc = (emergency.description or "").lower()
        
        # 1. Keyword scan
        detected_severity = SeverityLevel.P4_MINOR
        if any(k in desc for k in CRITICAL_KEYWORDS):
            detected_severity = SeverityLevel.P1_CRITICAL
        elif any(k in desc for k in URGENT_KEYWORDS):
            detected_severity = SeverityLevel.P2_URGENT
        elif any(k in desc for k in MODERATE_KEYWORDS):
            detected_severity = SeverityLevel.P3_MODERATE
            
        # 2. Category detection
        detected_category = "GENERAL"
        for cat, keywords in CATEGORY_MAP.items():
            if any(k in desc for k in keywords):
                detected_category = cat
                break
        
        # 3. Floor severity
        floor_severity = TYPE_SEVERITY_FLOOR.get(detected_category, SeverityLevel.P4_MINOR)
        
        # 4. Take most critical
        if SEVERITY_RANK[floor_severity] < SEVERITY_RANK[detected_severity]:
            final_severity = floor_severity
        else:
            final_severity = detected_severity
            
        emergency.severity = final_severity
        emergency.medical_category = detected_category
        
        confidence = 0.92 if final_severity == SeverityLevel.P1_CRITICAL else (0.85 if final_severity == SeverityLevel.P2_URGENT else 0.75)
        emergency.ai_confidence_score = confidence
        
        decision_text = f"Triaged as {final_severity} with category {detected_category}"
        reasoning = f"Keywords detected in description: '{desc}'. Applied floor severity for {detected_category}."
        
        # Create Log
        log_content = f"{emergency.id}-{datetime.utcnow().isoformat()}"
        decision_hash = hashlib.sha256(log_content.encode()).hexdigest()
        
        log = AgentLog(
            emergency_id=emergency.id,
            agent_name="TRIAGE_AGENT",
            decision=decision_text,
            reasoning=reasoning,
            confidence=confidence,
            decision_hash=decision_hash
        )
        db.add(log)
        await db.flush()
