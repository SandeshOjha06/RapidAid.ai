"""
GPS Simulator: Moves ambulances 8% closer to target every 3 seconds.
Run alongside server: python -m data_simulation.simulator
"""

import asyncio
import httpx
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.db_models import Vehicle, Emergency, EmergencyStatus


# Ambulance home positions (reset after arrival)
AMBULANCE_START_POSITIONS = {
    "KTM-T1-01": (27.7172, 85.3240),
    "KTM-T1-02": (27.7361, 85.3423),
    "KTM-T2-01": (27.6939, 85.3157),
    "KTM-T2-02": (27.7030, 85.3143),
    "KTM-T1-03": (27.7200, 85.3280),
}


async def simulate_gps_movement():
    """Main simulator loop: move vehicles every 3 seconds."""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    # Get all vehicles
                    vehicles = (await db.execute(select(Vehicle))).scalars().all()

                    for vehicle in vehicles:
                        # Check if vehicle has active emergency
                        active_emergency_stmt = select(Emergency).where(
                            (Emergency.vehicle_id == vehicle.id) &
                            (Emergency.status.in_([
                                EmergencyStatus.DISPATCHED,
                                EmergencyStatus.EN_ROUTE
                            ]))
                        )
                        emergency = (await db.execute(active_emergency_stmt)).scalar_one_or_none()

                        if emergency:
                            # Move 8% closer to patient, then hospital
                            current_lat, current_lng = vehicle.current_lat, vehicle.current_lng

                            # Determine target
                            if emergency.status == EmergencyStatus.DISPATCHED:
                                # Moving to patient
                                target_lat, target_lng = emergency.patient_lat, emergency.patient_lng
                            else:
                                # Moving to hospital (already picked up patient)
                                target_lat, target_lng = emergency.hospital.lat, emergency.hospital.lng

                            # Interpolate: move 8% closer
                            new_lat = current_lat + (target_lat - current_lat) * 0.08
                            new_lng = current_lng + (target_lng - current_lng) * 0.08

                            # Check arrival (within 0.0005 degrees ≈ 55 meters)
                            lat_delta = abs(new_lat - target_lat)
                            lng_delta = abs(new_lng - target_lng)

                            if lat_delta < 0.0005 and lng_delta < 0.0005:
                                # Arrived at patient or hospital
                                if emergency.status == EmergencyStatus.DISPATCHED:
                                    # Reached patient, now heading to hospital
                                    emergency.status = EmergencyStatus.EN_ROUTE
                                    await db.commit()
                                    print(f"🚗 {vehicle.registration} arrived at patient, heading to hospital")
                                else:
                                    # Reached hospital, reset vehicle
                                    vehicle.current_lat, vehicle.current_lng = AMBULANCE_START_POSITIONS[vehicle.registration]
                                    emergency.status = EmergencyStatus.ARRIVED
                                    vehicle.is_available = True
                                    await db.commit()
                                    print(f"🏥 {vehicle.registration} arrived at hospital, available again")
                            else:
                                # Update position via API
                                await client.patch(
                                    f"/vehicles/{vehicle.id}/location",
                                    json={"lat": new_lat, "lng": new_lng}
                                )
                                print(f"📍 {vehicle.registration}: ({new_lat:.4f}, {new_lng:.4f})")
                        else:
                            # No active emergency, reset to start position if needed
                            start_lat, start_lng = AMBULANCE_START_POSITIONS[vehicle.registration]
                            if (vehicle.current_lat, vehicle.current_lng) != (start_lat, start_lng):
                                vehicle.current_lat, vehicle.current_lng = start_lat, start_lng
                                db.add(vehicle)
                                await db.commit()

                await asyncio.sleep(3)  # Update every 3 seconds

            except Exception as e:
                print(f"❌ Simulator error: {e}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    print("🚀 Starting GPS Simulator...")
    print("📍 Ambulances will move 8% closer every 3 seconds")
    print("💡 Trigger a POST /emergency/sos to see ambulance movement")
    
    try:
        asyncio.run(simulate_gps_movement())
    except KeyboardInterrupt:
        print("\n🛑 Simulator stopped")
