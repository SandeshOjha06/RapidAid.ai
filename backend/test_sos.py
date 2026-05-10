import asyncio
from app.database import AsyncSessionLocal
from app.agents.pipeline import pipeline
from app.models.schemas import SOSRequest
import traceback

async def test():
    async with AsyncSessionLocal() as db:
        req = SOSRequest(
            patient_lat=27.7172,
            patient_lng=85.3240,
            patient_address="Thamel, Kathmandu",
            description="cardiac arrest, person unconscious, not breathing",
            emergency_type="CRITICAL_SOS",
            patient_name="Ram Bahadur Thapa",
            patient_phone="+977-9841234567"
        )
        try:
            emg = await pipeline.process_sos(req, db)
            print("SUCCESS:", emg.id)
        except Exception as e:
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
