"""
GPS Simulator: Moves ambulances 8% closer to target every 3 seconds.
Run alongside server: python -m data_simulation.simulator

The simulator reads from the DB and calls the backend API to update positions,
which in turn broadcasts WebSocket updates to patient tracking channels.
"""
import asyncio
import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=5.0) as client:
        while True:
            try:
                async with AsyncSessionLocal() as db:
                    # Fetch all vehicles
                    vehicles = (await db.execute(select(Vehicle))).scalars().all()

                    for vehicle in vehicles:
                        # BUG FIX: eager-load hospital relationship to avoid MissingGreenlet
                        active_stmt = (
                            select(Emergency)
                            .options(selectinload(Emergency.hospital))
                            .where(
                                Emergency.vehicle_id == vehicle.id,
                                Emergency.status.in_([
                                    EmergencyStatus.DISPATCHED,
                                    EmergencyStatus.EN_ROUTE,
                                ])
                            )
                        )
                        emergency = (await db.execute(active_stmt)).scalar_one_or_none()

                        if emergency:
                            current_lat = vehicle.current_lat
                            current_lng = vehicle.current_lng

                            if current_lat is None or current_lng is None:
                                continue  # Skip vehicles without GPS

                            # Determine target coordinates
                            if emergency.status == EmergencyStatus.DISPATCHED:
                                # Moving to patient
                                target_lat, target_lng = emergency.patient_lat, emergency.patient_lng
                                phase = "→ patient"
                            else:
                                # Moving to hospital (already picked up patient)
                                if not emergency.hospital:
                                    continue  # No hospital assigned yet
                                target_lat, target_lng = emergency.hospital.lat, emergency.hospital.lng
                                phase = "→ hospital"

                            # Interpolate: move 8% closer
                            new_lat = current_lat + (target_lat - current_lat) * 0.08
                            new_lng = current_lng + (target_lng - current_lng) * 0.08

                            # Arrival check (within ~55 meters)
                            arrived = abs(new_lat - target_lat) < 0.0005 and abs(new_lng - target_lng) < 0.0005

                            if arrived:
                                if emergency.status == EmergencyStatus.DISPATCHED:
                                    # Reached patient → now heading to hospital
                                    emergency.status = EmergencyStatus.EN_ROUTE
                                    db.add(emergency)
                                    await db.commit()
                                    print(f"🚗 {vehicle.registration} arrived at patient, heading to hospital")
                                else:
                                    # Reached hospital → reset vehicle
                                    start = AMBULANCE_START_POSITIONS.get(vehicle.registration)
                                    if start:
                                        vehicle.current_lat, vehicle.current_lng = start
                                    emergency.status = EmergencyStatus.ARRIVED
                                    vehicle.is_available = True
                                    db.add(emergency)
                                    db.add(vehicle)
                                    await db.commit()
                                    print(f"🏥 {vehicle.registration} arrived at hospital, now available")
                            else:
                                # Send GPS update through API (triggers WebSocket broadcast)
                                try:
                                    await client.patch(
                                        f"/vehicles/{vehicle.id}/location",
                                        json={"lat": new_lat, "lng": new_lng},
                                    )
                                    print(f"📍 {vehicle.registration} {phase}: ({new_lat:.4f}, {new_lng:.4f})")
                                except httpx.RequestError as req_err:
                                    print(f"⚠️  API call failed for {vehicle.registration}: {req_err}")

                        else:
                            # No active emergency — return to start position if displaced
                            start = AMBULANCE_START_POSITIONS.get(vehicle.registration)
                            if start and (vehicle.current_lat, vehicle.current_lng) != start:
                                vehicle.current_lat, vehicle.current_lng = start
                                db.add(vehicle)
                                await db.commit()

                await asyncio.sleep(3)

            except Exception as exc:
                print(f"❌ Simulator error: {exc}")
                await asyncio.sleep(5)


if __name__ == "__main__":
    print("🚀 Starting GPS Simulator...")
    print("📍 Ambulances move 8% closer to target every 3 seconds")
    print("💡 Trigger POST /emergency/sos to see movement in action")
    print("⏹  Press Ctrl+C to stop\n")
    try:
        asyncio.run(simulate_gps_movement())
    except KeyboardInterrupt:
        print("\n🛑 Simulator stopped")
