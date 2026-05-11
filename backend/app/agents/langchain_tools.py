import json
import logging
from typing import Optional, List, Dict
# pyrefly: ignore [missing-import]
from sqlalchemy import select
# pyrefly: ignore [missing-import]
from langchain_core.tools import tool

from app.models.db_models import Hospital, Vehicle, HospitalStatus, VehicleTier
from app.database import AsyncSessionLocal
from app.agents.web_search import search_nearest_hospitals_web, fetch_routing_info_web
from app.agents.agents import haversine_km

logger = logging.getLogger(__name__)

@tool
async def search_osm_hospitals_tool(lat: float, lng: float, query: str = "hospital") -> str:
    """
    Search OpenStreetMap for nearby hospitals or clinics around a given latitude and longitude.
    Returns a JSON string of hospital names, addresses, and coordinates.
    """
    try:
        results = await search_nearest_hospitals_web(lat, lng, query)
        if not results:
            return "No real-world hospitals found nearby."
        return json.dumps(results)
    except Exception as e:
        logger.error(f"search_osm_hospitals_tool failed: {e}")
        return f"Error occurred during web search: {e}"

@tool
async def calculate_route_tool(start_lat: float, start_lng: float, end_lat: float, end_lng: float) -> str:
    """
    Calculate the driving route between a start and end location using OSRM.
    Returns a JSON string containing "distance_km" and "duration_mins".
    If OSRM fails, it falls back to a Haversine straight-line distance calculation.
    """
    try:
        route = await fetch_routing_info_web(start_lat, start_lng, end_lat, end_lng)
        if route:
            return json.dumps(route)
        
        # Fallback to Haversine
        dist = haversine_km(start_lat, start_lng, end_lat, end_lng) * 1.3
        # Assume 35 km/h base speed for emergency
        duration = (dist / 35.0) * 60
        return json.dumps({"distance_km": dist, "duration_mins": duration, "note": "Fallback Haversine calculation"})
    except Exception as e:
        logger.error(f"calculate_route_tool failed: {e}")
        return f"Error occurred during route calculation: {e}"

@tool
async def query_db_hospitals_tool(severity_level: str, required_category: str, patient_lat: float, patient_lng: float) -> str:
    """
    Query the internal database for active hospitals.
    Args:
        severity_level: e.g. "P1_CRITICAL", "P2_URGENT", "P3_MODERATE"
        required_category: e.g. "CARDIAC", "TRAUMA", "GENERAL"
        patient_lat: Patient's latitude
        patient_lng: Patient's longitude
    Returns a JSON list of eligible hospital IDs, names, capacities, and straight-line distances.
    """
    async with AsyncSessionLocal() as db:
        stmt = select(Hospital).where(Hospital.is_active == True)
        result = await db.execute(stmt)
        hospitals = result.scalars().all()

        candidates = []
        for h in hospitals:
            if severity_level in ("P1_CRITICAL", "P2_URGENT") and h.icu_status != HospitalStatus.OPEN:
                continue
            if h.er_status != HospitalStatus.OPEN:
                continue

            dist = haversine_km(patient_lat, patient_lng, h.lat, h.lng) * 1.3
            candidates.append({
                "id": str(h.id),
                "name": h.name,
                "distance_km_approx": dist,
                "icu_status": h.icu_status.value,
                "er_status": h.er_status.value,
                "specializations": h.specializations
            })
            
        candidates.sort(key=lambda x: x["distance_km_approx"])
        # Return top 3
        return json.dumps(candidates[:3])

@tool
async def query_db_vehicles_tool(patient_lat: float, patient_lng: float, required_tier: str = "TIER_1") -> str:
    """
    Query the internal database for available ambulance vehicles.
    Args:
        patient_lat: Patient's latitude
        patient_lng: Patient's longitude
        required_tier: "TIER_1" (Advanced Life Support) or "TIER_2" (Basic)
    Returns a JSON list of available vehicle IDs, tiers, and straight-line distances to the patient.
    """
    async with AsyncSessionLocal() as db:
        stmt = select(Vehicle).where(
            Vehicle.is_available == True,
            Vehicle.current_lat.is_not(None),
            Vehicle.current_lng.is_not(None),
        )
        result = await db.execute(stmt)
        vehicles = result.scalars().all()

        candidates = []
        for v in vehicles:
            dist = haversine_km(patient_lat, patient_lng, v.current_lat, v.current_lng) * 1.3
            # Add a minor distance penalty if the tier isn't ideal, but include it anyway
            penalty = 0.0 if v.tier.value == required_tier else 1.5
            candidates.append({
                "id": str(v.id),
                "registration": v.registration,
                "tier": v.tier.value,
                "distance_km_approx": dist,
                "score": dist + penalty,
                "lat": v.current_lat,
                "lng": v.current_lng
            })

        candidates.sort(key=lambda x: x["score"])
        # Return top 3
        return json.dumps(candidates[:3])
