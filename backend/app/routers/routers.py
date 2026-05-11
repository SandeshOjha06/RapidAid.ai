from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select, func
from datetime import datetime, timedelta
from uuid import UUID
from typing import Optional
from app.models.db_models import (
    Emergency, Hospital, Vehicle, User, EmergencyStatus, 
    SeverityLevel, HospitalStatus
)
from app.models.schemas import (
    SOSRequest, EmergencyResponse, AgentDecisionResponse,
    HospitalStatusUpdate, VehicleLocationUpdate, DashboardStats
)
from app.database import AsyncSession, get_db
from app.agents.pipeline import pipeline
from app.websockets.manager import manager


# Emergency Router
emergency_router = APIRouter(prefix="/emergency", tags=["emergency"])
hospital_router = APIRouter(prefix="/hospitals", tags=["hospitals"])
vehicle_router = APIRouter(prefix="/vehicles", tags=["vehicles"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
ws_router = APIRouter(tags=["websockets"])


# ============ HEALTH CHECK ============
health_router = APIRouter(tags=["health"])

@health_router.get("/")
async def health_check():
    return {"status": "🟢 ONLINE", "service": "RapidAid.ai API"}


# ============ EMERGENCY ENDPOINTS ============
@emergency_router.post("/sos")
async def create_sos(request: SOSRequest, db: AsyncSession = Depends(get_db)) -> EmergencyResponse:
    """
    Core endpoint: Create emergency and run full 4-agent pipeline.
    Triggers WebSocket alerts to hospital and driver.
    """
    # Create or fetch patient if phone provided
    if request.patient_phone:
        stmt = select(User).where(User.phone == request.patient_phone)
        result = await db.execute(stmt)
        patient = result.scalar_one_or_none()
        if not patient:
            patient = User(
                name=request.patient_name or "Anonymous",
                phone=request.patient_phone,
                role="PATIENT"
            )
            db.add(patient)
            await db.flush()
    else:
        patient = None

    # Run pipeline (creates emergency and runs all agents)
    try:
        emergency = await pipeline.process_sos(request, db)
        emergency.patient_id = patient.id if patient else None
        await db.flush()
        await db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Refresh to get all relationships
    await db.refresh(emergency)

    # Broadcast WebSocket alerts
    if emergency.hospital_id:
        hospital_stmt = select(Hospital).where(Hospital.id == emergency.hospital_id)
        hospital = (await db.execute(hospital_stmt)).scalar_one()
        await manager.broadcast_hospital_incoming_patient(
            str(hospital.id),
            emergency.short_id,
            emergency.severity.value if emergency.severity else "UNKNOWN",
            emergency.medical_category or "GENERAL",
            emergency.estimated_eta_mins or 0,
            emergency.patient_lat,
            emergency.patient_lng
        )

    if emergency.vehicle_id:
        vehicle_stmt = select(Vehicle).where(Vehicle.id == emergency.vehicle_id)
        vehicle = (await db.execute(vehicle_stmt)).scalar_one()
        await manager.send_driver_assignment(
            str(vehicle.id),
            emergency.short_id,
            emergency.patient_lat,
            emergency.patient_lng,
            emergency.patient_address or "Unknown",
            emergency.severity.value if emergency.severity else "UNKNOWN"
        )

    return await _emergency_to_response(emergency, db)


@emergency_router.get("/{emergency_id}")
async def get_emergency(emergency_id: str, db: AsyncSession = Depends(get_db)) -> EmergencyResponse:
    """Get emergency by UUID or short_id."""
    try:
        query_id = UUID(emergency_id)
        stmt = select(Emergency).where((Emergency.id == query_id) | (Emergency.short_id == emergency_id))
    except ValueError:
        stmt = select(Emergency).where(Emergency.short_id == emergency_id)
        
    result = await db.execute(stmt)
    emergency = result.scalar_one_or_none()
    
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency not found")
    
    await db.refresh(emergency)
    return await _emergency_to_response(emergency, db)


@emergency_router.patch("/{emergency_id}/status")
async def update_emergency_status(
    emergency_id: str,
    status: EmergencyStatus = Query(...),
    db: AsyncSession = Depends(get_db)
) -> EmergencyResponse:
    """Update emergency status (ON_SCENE, ARRIVED, etc.)."""
    try:
        query_id = UUID(emergency_id)
        stmt = select(Emergency).where((Emergency.id == query_id) | (Emergency.short_id == emergency_id))
    except ValueError:
        stmt = select(Emergency).where(Emergency.short_id == emergency_id)
        
    result = await db.execute(stmt)
    emergency = result.scalar_one_or_none()
    
    if not emergency:
        raise HTTPException(status_code=404, detail="Emergency not found")

    # Update status and timestamps
    emergency.status = status
    if status == EmergencyStatus.ON_SCENE:
        emergency.on_scene_at = datetime.utcnow()
    elif status == EmergencyStatus.ARRIVED:
        emergency.arrived_at_hospital = datetime.utcnow()
        # Free up vehicle
        if emergency.vehicle_id:
            vehicle_stmt = select(Vehicle).where(Vehicle.id == emergency.vehicle_id)
            vehicle = (await db.execute(vehicle_stmt)).scalar_one()
            vehicle.is_available = True
            db.add(vehicle)

    db.add(emergency)
    await db.commit()

    # Broadcast to patient
    await manager.broadcast_patient_status_update(
        str(emergency.id),
        status.value
    )

    await db.refresh(emergency)
    return await _emergency_to_response(emergency, db)


# ============ HOSPITAL ENDPOINTS ============
@hospital_router.get("/")
async def list_hospitals(db: AsyncSession = Depends(get_db)):
    """List all active hospitals."""
    stmt = select(Hospital).where(Hospital.is_active == True)
    result = await db.execute(stmt)
    hospitals = result.scalars().all()
    
    return [
        {
            "id": str(h.id),
            "name": h.name,
            "phone": h.phone,
            "address": h.address,
            "lat": h.lat,
            "lng": h.lng,
            "specializations": h.specializations,
            "icu_status": h.icu_status.value,
            "er_status": h.er_status.value,
            "blood_bank": h.blood_bank,
            "operating_room": h.operating_room
        }
        for h in hospitals
    ]


@hospital_router.patch("/{hospital_id}/status")
async def update_hospital_status(
    hospital_id: str,
    update: HospitalStatusUpdate,
    db: AsyncSession = Depends(get_db)
):
    """1-click toggle for ICU/ER status."""
    try:
        hospital_uuid = UUID(hospital_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid hospital_id format")

    stmt = select(Hospital).where(Hospital.id == hospital_uuid)
    result = await db.execute(stmt)
    hospital = result.scalar_one_or_none()
    
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    if update.icu_status:
        hospital.icu_status = update.icu_status
    if update.er_status:
        hospital.er_status = update.er_status
    if update.blood_bank is not None:
        hospital.blood_bank = update.blood_bank
    if update.operating_room is not None:
        hospital.operating_room = update.operating_room

    db.add(hospital)
    await db.commit()

    return {
        "id": str(hospital.id),
        "name": hospital.name,
        "icu_status": hospital.icu_status.value,
        "er_status": hospital.er_status.value,
        "blood_bank": hospital.blood_bank,
        "operating_room": hospital.operating_room
    }


# ============ VEHICLE ENDPOINTS ============
@vehicle_router.get("/")
async def list_vehicles(db: AsyncSession = Depends(get_db)):
    """List all vehicles with driver info."""
    stmt = select(Vehicle)
    result = await db.execute(stmt)
    vehicles = result.scalars().all()

    response = []
    for v in vehicles:
        await db.refresh(v, ["driver"])
        driver_name = v.driver.name if v.driver else "Unassigned"
        driver_phone = v.driver.phone if v.driver else None
        
        response.append({
            "id": str(v.id),
            "registration": v.registration,
            "tier": v.tier.value,
            "is_available": v.is_available,
            "current_lat": v.current_lat,
            "current_lng": v.current_lng,
            "driver_name": driver_name,
            "driver_phone": driver_phone
        })

    return response


@vehicle_router.get("/{vehicle_id}/assignment")
async def get_vehicle_assignment(vehicle_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the active assignment for a vehicle if it exists (for when the driver portal reloads)."""
    try:
        vehicle_uuid = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vehicle_id")

    stmt = select(Emergency).where(
        (Emergency.vehicle_id == vehicle_uuid) & 
        (Emergency.status.in_([EmergencyStatus.DISPATCHED, EmergencyStatus.EN_ROUTE, EmergencyStatus.ON_SCENE, EmergencyStatus.TRANSPORTING]))
    ).order_by(Emergency.created_at.desc())
    result = await db.execute(stmt)
    emergency = result.scalars().first()
    
    if not emergency:
        return None
        
    return {
        "event": "ASSIGNMENT",
        "emergency_id": str(emergency.id),
        "short_id": emergency.short_id,
        "patient_lat": emergency.patient_lat,
        "patient_lng": emergency.patient_lng,
        "patient_address": emergency.patient_address,
        "severity": emergency.severity.value if emergency.severity else "UNKNOWN",
        "status": emergency.status.value
    }



@vehicle_router.patch("/{vehicle_id}/location")
async def update_vehicle_location(
    vehicle_id: str,
    update: VehicleLocationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Driver GPS ping. Broadcast to patient if vehicle has active emergency."""
    try:
        vehicle_uuid = UUID(vehicle_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid vehicle_id format")

    stmt = select(Vehicle).where(Vehicle.id == vehicle_uuid)
    result = await db.execute(stmt)
    vehicle = result.scalar_one_or_none()
    
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    vehicle.current_lat = update.lat
    vehicle.current_lng = update.lng
    db.add(vehicle)
    await db.commit()

    # Check if vehicle has active emergency and broadcast location
    emergency_stmt = select(Emergency).where(
        (Emergency.vehicle_id == vehicle.id) & 
        (Emergency.status.in_([EmergencyStatus.DISPATCHED, EmergencyStatus.EN_ROUTE]))
    ).order_by(Emergency.created_at.desc())
    emergency_result = await db.execute(emergency_stmt)
    emergency = emergency_result.scalars().first()

    if emergency:
        await manager.broadcast_patient_vehicle_location(
            str(emergency.id),
            update.lat,
            update.lng,
            emergency.estimated_eta_mins or 0
        )

    return {
        "id": str(vehicle.id),
        "registration": vehicle.registration,
        "current_lat": vehicle.current_lat,
        "current_lng": vehicle.current_lng
    }


# ============ DASHBOARD ENDPOINTS ============
@dashboard_router.get("/stats")
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)) -> DashboardStats:
    """Get live dashboard statistics."""
    
    # Active emergencies
    active_stmt = select(func.count(Emergency.id)).where(
        Emergency.status.in_([
            EmergencyStatus.PENDING, EmergencyStatus.TRIAGED,
            EmergencyStatus.DISPATCHED, EmergencyStatus.EN_ROUTE,
            EmergencyStatus.ON_SCENE, EmergencyStatus.TRANSPORTING
        ])
    )
    active_count = (await db.execute(active_stmt)).scalar() or 0

    # Available vehicles
    available_stmt = select(func.count(Vehicle.id)).where(Vehicle.is_available == True)
    available_count = (await db.execute(available_stmt)).scalar() or 0

    # Hospitals at capacity
    at_capacity_stmt = select(func.count(Hospital.id)).where(
        (Hospital.icu_status == HospitalStatus.FULL) | (Hospital.er_status == HospitalStatus.FULL)
    )
    at_capacity_count = (await db.execute(at_capacity_stmt)).scalar() or 0

    # Average response time (eta of emergencies from last 24h)
    today_start = datetime.utcnow() - timedelta(days=1)
    avg_eta_stmt = select(func.avg(Emergency.estimated_eta_mins)).where(
        Emergency.created_at >= today_start
    )
    avg_eta = (await db.execute(avg_eta_stmt)).scalar() or 0.0

    # Total emergencies today
    total_today_stmt = select(func.count(Emergency.id)).where(
        Emergency.created_at >= today_start
    )
    total_today = (await db.execute(total_today_stmt)).scalar() or 0

    return DashboardStats(
        active_emergencies=active_count,
        available_vehicles=available_count,
        hospitals_at_capacity=at_capacity_count,
        avg_response_time_mins=float(avg_eta),
        total_emergencies_today=total_today
    )


# ============ WEBSOCKET ENDPOINTS ============
@ws_router.websocket("/ws/patient/{emergency_id}")
async def websocket_patient_tracking(websocket: WebSocket, emergency_id: str):
    """Patient tracking WebSocket: vehicle location + status updates."""
    await manager.connect_patient(emergency_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Clients can only receive, not send on this channel
    except WebSocketDisconnect:
        manager.disconnect_patient(emergency_id, websocket)


@ws_router.websocket("/ws/driver/{vehicle_id}")
async def websocket_driver_assignment(websocket: WebSocket, vehicle_id: str):
    """Driver WebSocket: receive assignments, send GPS updates."""
    await manager.connect_driver(vehicle_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("event") == "GPS_UPDATE":
                lat = data.get("lat")
                lng = data.get("lng")
                # In production, validate and process GPS updates
                # For now, clients handle this via PATCH /vehicles/{id}/location
    except WebSocketDisconnect:
        manager.disconnect_driver(vehicle_id)


@ws_router.websocket("/ws/hospital/{hospital_id}")
async def websocket_hospital_alerts(websocket: WebSocket, hospital_id: str):
    """Hospital WebSocket: incoming patient alerts."""
    await manager.connect_hospital(hospital_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Hospitals can only receive, not send on this channel
    except WebSocketDisconnect:
        manager.disconnect_hospital(hospital_id, websocket)


# ============ HELPER FUNCTIONS ============
async def _emergency_to_response(emergency: Emergency, db: AsyncSession) -> EmergencyResponse:
    """Convert Emergency ORM to EmergencyResponse schema."""
    await db.refresh(emergency, ["vehicle", "hospital", "agent_logs"])

    vehicle_registration = None
    if emergency.vehicle_id:
        vehicle_stmt = select(Vehicle).where(Vehicle.id == emergency.vehicle_id)
        vehicle = (await db.execute(vehicle_stmt)).scalar_one()
        vehicle_registration = vehicle.registration

    hospital_name = None
    hospital_address = None
    hospital_phone = None
    hospital_lat = None
    hospital_lng = None
    if emergency.hospital_id:
        hospital = emergency.hospital
        hospital_name = hospital.name
        hospital_address = hospital.address
        hospital_phone = hospital.phone
        hospital_lat = hospital.lat
        hospital_lng = hospital.lng

    agent_decisions = [
        AgentDecisionResponse(
            agent_name=log.agent_name,
            decision=log.decision,
            reasoning=log.reasoning,
            confidence=log.confidence,
            created_at=log.created_at
        )
        for log in emergency.agent_logs
    ]

    return EmergencyResponse(
        id=emergency.id,
        short_id=emergency.short_id,
        status=emergency.status,
        severity=emergency.severity,
        medical_category=emergency.medical_category,
        estimated_eta_mins=emergency.estimated_eta_mins,
        fare_npr=emergency.fare_npr,
        vehicle_registration=vehicle_registration,
        hospital_name=hospital_name,
        hospital_address=hospital_address,
        hospital_phone=hospital_phone,
        hospital_lat=hospital_lat,
        hospital_lng=hospital_lng,
        tracking_ws_url=f"/ws/patient/{emergency.id}" if emergency.id else None,
        agent_decisions=agent_decisions,
        created_at=emergency.created_at
    )
