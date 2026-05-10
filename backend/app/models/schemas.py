from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.db_models import UserRole, VehicleTier, SeverityLevel, EmergencyType, EmergencyStatus, HospitalStatus

class SOSRequest(BaseModel):
    patient_lat: float = Field(..., ge=-90, le=90)
    patient_lng: float = Field(..., ge=-180, le=180)
    patient_address: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    emergency_type: EmergencyType = EmergencyType.CRITICAL_SOS
    patient_name: Optional[str] = "Anonymous"
    patient_phone: Optional[str] = None

class AgentDecisionResponse(BaseModel):
    agent_name: str
    decision: str
    reasoning: str
    confidence: float
    created_at: datetime
    class Config:
        from_attributes = True

class EmergencyResponse(BaseModel):
    id: UUID
    short_id: str
    status: EmergencyStatus
    severity: Optional[SeverityLevel] = None
    medical_category: Optional[str] = None
    estimated_eta_mins: Optional[int] = None
    fare_npr: Optional[float] = None
    vehicle_registration: Optional[str] = None
    hospital_name: Optional[str] = None
    hospital_address: Optional[str] = None
    hospital_phone: Optional[str] = None
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None
    tracking_ws_url: Optional[str] = None
    agent_decisions: List[AgentDecisionResponse] = []
    created_at: datetime
    class Config:
        from_attributes = True

class HospitalStatusUpdate(BaseModel):
    icu_status: Optional[HospitalStatus] = None
    er_status: Optional[HospitalStatus] = None
    blood_bank: Optional[bool] = None
    operating_room: Optional[bool] = None

class VehicleLocationUpdate(BaseModel):
    lat: float
    lng: float

class DashboardStats(BaseModel):
    active_emergencies: int
    available_vehicles: int
    hospitals_at_capacity: int
    avg_response_time_mins: float
    total_emergencies_today: int
