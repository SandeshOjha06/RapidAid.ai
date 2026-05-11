import enum
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, Enum, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    DRIVER = "DRIVER"
    HOSPITAL_STAFF = "HOSPITAL_STAFF"
    ADMIN = "ADMIN"

class VehicleTier(str, enum.Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"

class SeverityLevel(str, enum.Enum):
    P1_CRITICAL = "P1_CRITICAL"
    P2_URGENT = "P2_URGENT"
    P3_MODERATE = "P3_MODERATE"
    P4_MINOR = "P4_MINOR"

class EmergencyType(str, enum.Enum):
    CRITICAL_SOS = "CRITICAL_SOS"
    MEDICAL_RIDE = "MEDICAL_RIDE"

class EmergencyStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRIAGED = "TRIAGED"
    DISPATCHED = "DISPATCHED"
    EN_ROUTE = "EN_ROUTE"
    ON_SCENE = "ON_SCENE"
    TRANSPORTING = "TRANSPORTING"
    ARRIVED = "ARRIVED"
    CLOSED = "CLOSED"

class HospitalStatus(str, enum.Enum):
    OPEN = "OPEN"
    FULL = "FULL"
    OFFLINE = "OFFLINE"

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(150), unique=True, nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.PATIENT)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    current_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emergencies_as_patient: Mapped[List["Emergency"]] = relationship("Emergency", back_populates="patient")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", back_populates="driver", uselist=False)

class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    specializations: Mapped[List[str]] = mapped_column(JSON, default=[])
    icu_status: Mapped[HospitalStatus] = mapped_column(Enum(HospitalStatus), default=HospitalStatus.OPEN)
    er_status: Mapped[HospitalStatus] = mapped_column(Enum(HospitalStatus), default=HospitalStatus.OPEN)
    blood_bank: Mapped[bool] = mapped_column(Boolean, default=False)
    operating_room: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    emergencies: Mapped[List["Emergency"]] = relationship("Emergency", back_populates="hospital")

class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    registration: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    tier: Mapped[VehicleTier] = mapped_column(Enum(VehicleTier), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    current_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    current_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    driver_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    driver: Mapped[Optional["User"]] = relationship("User", back_populates="vehicle")
    emergencies: Mapped[List["Emergency"]] = relationship("Emergency", back_populates="vehicle")

class Emergency(Base):
    __tablename__ = "emergencies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    short_id: Mapped[str] = mapped_column(String(12), unique=True, nullable=False)
    patient_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    patient_lat: Mapped[float] = mapped_column(Float, nullable=False)
    patient_lng: Mapped[float] = mapped_column(Float, nullable=False)
    patient_address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    emergency_type: Mapped[EmergencyType] = mapped_column(Enum(EmergencyType), default=EmergencyType.CRITICAL_SOS)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    voice_note_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    severity: Mapped[Optional[SeverityLevel]] = mapped_column(Enum(SeverityLevel), nullable=True)
    medical_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vehicle_id: Mapped[Optional[str]] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    hospital_id: Mapped[Optional[str]] = mapped_column(ForeignKey("hospitals.id"), nullable=True)
    estimated_eta_mins: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fare_npr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[EmergencyStatus] = mapped_column(Enum(EmergencyStatus), default=EmergencyStatus.PENDING)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    on_scene_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    arrived_at_hospital: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    patient: Mapped[Optional["User"]] = relationship("User", back_populates="emergencies_as_patient")
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", back_populates="emergencies")
    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", back_populates="emergencies")
    agent_logs: Mapped[List["AgentLog"]] = relationship("AgentLog", back_populates="emergency", order_by="AgentLog.created_at")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    emergency_id: Mapped[str] = mapped_column(ForeignKey("emergencies.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False) # "TRIAGE_AGENT", etc.
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    decision_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    emergency: Mapped["Emergency"] = relationship("Emergency", back_populates="agent_logs")
