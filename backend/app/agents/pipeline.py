"""
AgentPipeline — Orchestrates all 5 agents for emergency dispatch.

Pipeline sequence:
  1. SmartTriageAgent  (Gemini → rule-based fallback)
  2. HospitalAgent     (nearest capable hospital)
  3. NegotiationAgent  (confirm hospital capacity, re-route if needed)
  4. DispatchAgent     (nearest available ambulance)
  5. RouteAgent        (ETA + fare calculation)

Transaction boundary: The pipeline does NOT commit. The caller (router)
owns the commit so it can attach patient_id before finalizing.
"""
import logging
import uuid
from datetime import datetime

from app.agents.gemini_triage import SmartTriageAgent
from app.agents.agents import HospitalAgent, NegotiationAgent, DispatchAgent, RouteAgent
from app.models.db_models import Emergency, EmergencyStatus
from app.models.schemas import SOSRequest
from app.database import AsyncSession

logger = logging.getLogger(__name__)


class AgentPipeline:
    def __init__(self):
        self.triage_agent      = SmartTriageAgent()
        self.hospital_agent    = HospitalAgent()
        self.negotiation_agent = NegotiationAgent()
        self.dispatch_agent    = DispatchAgent()
        self.route_agent       = RouteAgent()

    async def process_sos(self, request: SOSRequest, db: AsyncSession) -> Emergency:
        """
        Execute the full 5-agent pipeline for emergency dispatch.

        Returns the Emergency ORM object with all relationships populated.
        Does NOT commit — caller must call db.commit() after attaching patient_id.
        Raises on any agent failure and rolls back.
        """
        pipeline_start = datetime.utcnow()

        try:
            # ── Create Emergency record ──────────────────────────────────────
            short_id = f"EMG-{uuid.uuid4().hex[:4].upper()}"
            emergency = Emergency(
                short_id=short_id,
                patient_lat=request.patient_lat,
                patient_lng=request.patient_lng,
                patient_address=request.patient_address,
                description=request.description,
                image_url=request.image_url,
                emergency_type=request.emergency_type,
                status=EmergencyStatus.PENDING,
            )
            db.add(emergency)
            await db.flush()  # Get emergency.id without committing

            logger.info("Pipeline started for %s (%s)", short_id, request.emergency_type)

            # ── Agent 1: Smart Triage (Gemini / rule-based) ──────────────────
            t0 = datetime.utcnow()
            await self.triage_agent.process(emergency, db)
            emergency.status = EmergencyStatus.TRIAGED
            await db.flush()
            logger.info("[1/5] TriageAgent done in %.0fms", (datetime.utcnow() - t0).total_seconds() * 1000)

            # ── Agent 2: Hospital Selection ──────────────────────────────────
            t0 = datetime.utcnow()
            await self.hospital_agent.process(emergency, db)
            await db.flush()
            logger.info("[2/5] HospitalAgent done in %.0fms", (datetime.utcnow() - t0).total_seconds() * 1000)

            # ── Agent 3: Hospital Capacity Negotiation ───────────────────────
            t0 = datetime.utcnow()
            await self.negotiation_agent.process(emergency, db)
            await db.flush()
            logger.info("[3/5] NegotiationAgent done in %.0fms", (datetime.utcnow() - t0).total_seconds() * 1000)

            # ── Agent 4: Dispatch Vehicle ────────────────────────────────────
            t0 = datetime.utcnow()
            await self.dispatch_agent.process(emergency, db)
            await db.flush()
            logger.info("[4/5] DispatchAgent done in %.0fms", (datetime.utcnow() - t0).total_seconds() * 1000)

            # ── Agent 5: Route & ETA ─────────────────────────────────────────
            t0 = datetime.utcnow()
            await self.route_agent.process(emergency, db)
            await db.flush()
            logger.info("[5/5] RouteAgent done in %.0fms", (datetime.utcnow() - t0).total_seconds() * 1000)

            total_ms = (datetime.utcnow() - pipeline_start).total_seconds() * 1000
            logger.info(
                "Pipeline complete for %s → severity=%s, hospital_id=%s, vehicle_id=%s, eta=%s min [%.0fms total]",
                short_id,
                emergency.severity.value if emergency.severity else "?",
                emergency.hospital_id,
                emergency.vehicle_id,
                emergency.estimated_eta_mins,
                total_ms,
            )

            # ── NOTE: Do NOT commit here. Caller owns transaction. ───────────
            return emergency

        except Exception as exc:
            logger.error("Pipeline failed for request %s: %s", request.patient_address, exc, exc_info=True)
            await db.rollback()
            raise


# Global singleton — safe because AgentPipeline is stateless (all state is in DB)
pipeline = AgentPipeline()
