import math
import hashlib
from datetime import datetime
from sqlalchemy import select
from app.models.db_models import (
    Emergency, Hospital, Vehicle, AgentLog, SeverityLevel, 
    HospitalStatus, VehicleTier, EmergencyStatus
)
from app.database import AsyncSession

def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1; dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(a))

class HospitalAgent:
    async def process(self, emergency: Emergency, db: AsyncSession):
        stmt = select(Hospital).where(Hospital.is_active == True)
        result = await db.execute(stmt)
        hospitals = result.scalars().all()
        
        candidates = []
        for h in hospitals:
            # Filter
            if emergency.severity in [SeverityLevel.P1_CRITICAL, SeverityLevel.P2_URGENT]:
                if h.icu_status != HospitalStatus.OPEN: continue
            if h.er_status != HospitalStatus.OPEN: continue
            
            # Specialization match
            spec_match = False
            if emergency.medical_category == "GENERAL" or not emergency.medical_category:
                spec_match = True
            elif emergency.medical_category in h.specializations:
                spec_match = True
            
            dist = haversine_km(emergency.patient_lat, emergency.patient_lng, h.lat, h.lng) * 1.3
            spec_bonus = 0 if spec_match else 2.0
            score = dist + spec_bonus
            candidates.append((score, h))
            
        if not candidates:
            # Fallback
            stmt = select(Hospital).where(Hospital.er_status == HospitalStatus.OPEN)
            result = await db.execute(stmt)
            fallback_hospitals = result.scalars().all()
            if fallback_hospitals:
                selected_hospital = fallback_hospitals[0]
            else:
                raise Exception("No available hospitals found even in fallback!")
        else:
            candidates.sort(key=lambda x: x[0])
            selected_hospital = candidates[0][1]
            
        emergency.hospital_id = selected_hospital.id
        
        log = AgentLog(
            emergency_id=emergency.id,
            agent_name="HOSPITAL_AGENT",
            decision=f"Selected {selected_hospital.name}",
            reasoning=f"Optimal hospital based on severity {emergency.severity} and location.",
            confidence=0.90,
            decision_hash=hashlib.sha256(f"{emergency.id}-HOSPITAL-{datetime.utcnow()}".encode()).hexdigest()
        )
        db.add(log)
        await db.flush()

class DispatchAgent:
    async def process(self, emergency: Emergency, db: AsyncSession):
        TIER_SEVERITY_MAP = {
            SeverityLevel.P1_CRITICAL: [VehicleTier.TIER_1],
            SeverityLevel.P2_URGENT:   [VehicleTier.TIER_1, VehicleTier.TIER_2],
            SeverityLevel.P3_MODERATE: [VehicleTier.TIER_2, VehicleTier.TIER_1],
            SeverityLevel.P4_MINOR:    [VehicleTier.TIER_2],
        }
        
        stmt = select(Vehicle).where(Vehicle.is_available == True, Vehicle.current_lat != None)
        result = await db.execute(stmt)
        vehicles = result.scalars().all()
        
        preferred_tiers = TIER_SEVERITY_MAP.get(emergency.severity, [VehicleTier.TIER_2])
        
        candidates = []
        for v in vehicles:
            dist = haversine_km(emergency.patient_lat, emergency.patient_lng, v.current_lat, v.current_lng) * 1.3
            tier_penalty = 0 if v.tier in preferred_tiers else 1.5
            score = dist + tier_penalty
            candidates.append((score, v))
            
        if not candidates:
             raise Exception("No available vehicles found!")
             
        candidates.sort(key=lambda x: x[0])
        selected_vehicle = candidates[0][1]
        
        emergency.vehicle_id = selected_vehicle.id
        emergency.status = EmergencyStatus.DISPATCHED
        emergency.dispatched_at = datetime.utcnow()
        
        selected_vehicle.is_available = False
        db.add(selected_vehicle)
        
        log = AgentLog(
            emergency_id=emergency.id,
            agent_name="DISPATCH_AGENT",
            decision=f"Dispatched {selected_vehicle.registration}",
            reasoning=f"Closest available vehicle with tier {selected_vehicle.tier}.",
            confidence=0.94,
            decision_hash=hashlib.sha256(f"{emergency.id}-DISPATCH-{datetime.utcnow()}".encode()).hexdigest()
        )
        db.add(log)
        await db.flush()

class RouteAgent:
    async def process(self, emergency: Emergency, db: AsyncSession):
        # Fetch hospital and vehicle for locations
        hospital_stmt = select(Hospital).where(Hospital.id == emergency.hospital_id)
        hospital = (await db.execute(hospital_stmt)).scalar_one()
        
        vehicle_stmt = select(Vehicle).where(Vehicle.id == emergency.vehicle_id)
        vehicle = (await db.execute(vehicle_stmt)).scalar_one()
        
        # Traffic by hour Kathmandu (UTC+5:45 assumed, but using server hour for simplicity)
        hour = datetime.utcnow().hour
        traffic_mult = 1.3
        if 0 <= hour < 6: traffic_mult = 0.7
        elif 6 <= hour < 8: traffic_mult = 1.2
        elif 8 <= hour < 11: traffic_mult = 1.8
        elif 11 <= hour < 17: traffic_mult = 1.3
        elif 17 <= hour < 20: traffic_mult = 1.9
        elif 20 <= hour < 24: traffic_mult = 1.1

        speed = 35 if emergency.emergency_type == "CRITICAL_SOS" else 25
        effective_mult = 1 + (traffic_mult - 1) * 0.4
        
        dist1 = haversine_km(vehicle.current_lat, vehicle.current_lng, emergency.patient_lat, emergency.patient_lng) * 1.3
        dist2 = haversine_km(emergency.patient_lat, emergency.patient_lng, hospital.lat, hospital.lng) * 1.3
        
        total_dist = dist1 + dist2
        eta_mins = max(2, round((total_dist / speed) * 60 * effective_mult))
        
        emergency.estimated_eta_mins = eta_mins
        
        if emergency.emergency_type == "MEDICAL_RIDE":
            tier_mult = 2.5 if vehicle.tier == VehicleTier.TIER_1 else 1.0
            emergency.fare_npr = (200.0 + total_dist * 35.0) * tier_mult
            
        log = AgentLog(
            emergency_id=emergency.id,
            agent_name="ROUTE_AGENT",
            decision=f"ETA: {eta_mins} mins",
            reasoning=f"Distance: {total_dist:.2f}km. Traffic multiplier: {traffic_mult}. Nepal traffic context applied.",
            confidence=0.88,
            decision_hash=hashlib.sha256(f"{emergency.id}-ROUTE-{datetime.utcnow()}".encode()).hexdigest()
        )
        db.add(log)
        await db.flush()
