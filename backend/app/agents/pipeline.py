import uuid
from app.agents.triage_agent import TriageAgent
from app.agents.agents import HospitalAgent, DispatchAgent, RouteAgent
from app.models.db_models import Emergency, EmergencyStatus
from app.models.schemas import SOSRequest
from app.database import AsyncSession


class AgentPipeline:
    def __init__(self):
        self.triage_agent = TriageAgent()
        self.hospital_agent = HospitalAgent()
        self.dispatch_agent = DispatchAgent()
        self.route_agent = RouteAgent()

    async def process_sos(self, request: SOSRequest, db: AsyncSession) -> Emergency:
        """Execute the full 4-agent pipeline for emergency dispatch."""
        try:
            # 1. Create Emergency record
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
            await db.flush()

            # 2. Run agents in sequence
            # Agent 1: Triage
            await self.triage_agent.process(emergency, db)
            emergency.status = EmergencyStatus.TRIAGED
            await db.flush()

            # Agent 2: Hospital Selection
            await self.hospital_agent.process(emergency, db)
            await db.flush()

            # Agent 3: Dispatch Vehicle
            await self.dispatch_agent.process(emergency, db)
            await db.flush()

            # Agent 4: Route & ETA
            await self.route_agent.process(emergency, db)
            await db.flush()

            # 3. Commit all changes atomically
            await db.commit()

            # Refresh to get relationships
            await db.refresh(emergency)
            return emergency

        except Exception as e:
            await db.rollback()
            raise e


# Global singleton
pipeline = AgentPipeline()
