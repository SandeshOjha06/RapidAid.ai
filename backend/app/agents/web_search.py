import httpx
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

async def search_nearest_hospitals_web(lat: float, lng: float, query: str = "hospital") -> List[Dict]:
    """
    Fallback web search for nearest hospitals using OpenStreetMap Nominatim API.
    Used by the Hospital Agent to enrich its internal DB data.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "json",
        "q": query,
        "lat": lat,
        "lon": lng,
        "limit": 5,
        "addressdetails": 1
    }
    headers = {"User-Agent": "RapidAid.ai/1.0"}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data:
                    results.append({
                        "name": item.get("name", "Unknown Hospital"),
                        "lat": float(item.get("lat")),
                        "lon": float(item.get("lon")),
                        "address": item.get("display_name", "")
                    })
                return results
            else:
                logger.warning("Nominatim API returned status %s", response.status_code)
                return []
    except Exception as e:
        logger.error("Web search failed: %s", e)
        return []

async def fetch_routing_info_web(start_lat: float, start_lng: float, end_lat: float, end_lng: float) -> Optional[Dict]:
    """
    Fetch routing ETA and distance using OSRM (Open Source Routing Machine) public API.
    Used by the Route Agent.
    """
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lng},{start_lat};{end_lng},{end_lat}?overview=false"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if "routes" in data and len(data["routes"]) > 0:
                    route = data["routes"][0]
                    return {
                        "distance_km": route.get("distance", 0) / 1000.0,
                        "duration_mins": route.get("duration", 0) / 60.0
                    }
            return None
    except Exception as e:
        logger.error("OSRM Routing API failed: %s", e)
        return None
