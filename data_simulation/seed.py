"""
Seeds demo data: 6 real Kathmandu hospitals + 5 vehicles + 3 demo users
Called automatically on startup if DEMO_MODE=True
"""

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.db_models import (
    Hospital, Vehicle, User, UserRole, VehicleTier,
    HospitalStatus
)


HOSPITALS = [
    {
        "name": "Tribhuvan University Teaching Hospital (TUTH)",
        "phone": "01-4412404",
        "address": "Maharajgunj, Kathmandu",
        "lat": 27.7330,
        "lng": 85.3295,
        "specializations": ["TRAUMA", "CARDIAC", "NEURO", "GENERAL"],
        "icu_status": HospitalStatus.OPEN,
        "er_status": HospitalStatus.OPEN,
        "blood_bank": True,
        "operating_room": True,
    },
    {
        "name": "Bir Hospital",
        "phone": "01-4221119",
        "address": "Kanti Path, Kathmandu",
        "lat": 27.7042,
        "lng": 85.3144,
        "specializations": ["TRAUMA", "GENERAL"],
        "icu_status": HospitalStatus.FULL,
        "er_status": HospitalStatus.OPEN,
        "blood_bank": True,
        "operating_room": True,
    },
    {
        "name": "Paropakar Maternity & Women's Hospital",
        "phone": "01-4215429",
        "address": "Thapathali, Kathmandu",
        "lat": 27.6980,
        "lng": 85.3095,
        "specializations": ["MATERNITY"],
        "icu_status": HospitalStatus.OPEN,
        "er_status": HospitalStatus.OPEN,
        "blood_bank": True,
        "operating_room": True,
    },
    {
        "name": "Norvic International Hospital",
        "phone": "01-5970032",
        "address": "Thapathali, Kathmandu",
        "lat": 27.6914,
        "lng": 85.3128,
        "specializations": ["CARDIAC", "GENERAL"],
        "icu_status": HospitalStatus.OPEN,
        "er_status": HospitalStatus.OPEN,
        "blood_bank": True,
        "operating_room": True,
    },
    {
        "name": "Grande International Hospital",
        "phone": "01-5159266",
        "address": "Tokha Road, Kathmandu",
        "lat": 27.7394,
        "lng": 85.3217,
        "specializations": ["TRAUMA", "CARDIAC", "NEURO"],
        "icu_status": HospitalStatus.OPEN,
        "er_status": HospitalStatus.OPEN,
        "blood_bank": True,
        "operating_room": True,
    },
    {
        "name": "Kathmandu Medical College Teaching Hospital",
        "phone": "01-4477497",
        "address": "Sinamangal, Kathmandu",
        "lat": 27.6960,
        "lng": 85.3490,
        "specializations": ["GENERAL", "TRAUMA"],
        "icu_status": HospitalStatus.OPEN,
        "er_status": HospitalStatus.OPEN,
        "blood_bank": False,
        "operating_room": True,
    },
]

VEHICLES = [
    {
        "registration": "KTM-T1-01",
        "tier": VehicleTier.TIER_1,
        "lat": 27.7172,
        "lng": 85.3240,
        "driver_name": "Bikash Tamang",
        "driver_phone": "+977-9841000001",
    },
    {
        "registration": "KTM-T1-02",
        "tier": VehicleTier.TIER_1,
        "lat": 27.7361,
        "lng": 85.3423,
        "driver_name": "Ramesh KC",
        "driver_phone": "+977-9841000002",
    },
    {
        "registration": "KTM-T2-01",
        "tier": VehicleTier.TIER_2,
        "lat": 27.6939,
        "lng": 85.3157,
        "driver_name": "Sita Rai",
        "driver_phone": "+977-9841000003",
    },
    {
        "registration": "KTM-T2-02",
        "tier": VehicleTier.TIER_2,
        "lat": 27.7030,
        "lng": 85.3143,
        "driver_name": "Priya Gurung",
        "driver_phone": "+977-9841000004",
    },
    {
        "registration": "KTM-T1-03",
        "tier": VehicleTier.TIER_1,
        "lat": 27.7200,
        "lng": 85.3280,
        "driver_name": "Arjun Shrestha",
        "driver_phone": "+977-9841000005",
    },
]

DEMO_USERS = [
    {
        "name": "Demo Patient",
        "phone": "+977-9841111111",
        "email": "patient@demo.com",
        "role": UserRole.PATIENT,
        "hashed_password": "demo1234",
    },
    {
        "name": "Demo Hospital",
        "phone": "+977-9842222222",
        "email": "hospital@demo.com",
        "role": UserRole.HOSPITAL_STAFF,
        "hashed_password": "demo1234",
    },
    {
        "name": "Admin",
        "phone": "+977-9843333333",
        "email": "admin@demo.com",
        "role": UserRole.ADMIN,
        "hashed_password": "demo1234",
    },
]


async def seed_demo_data():
    """Seed hospitals, vehicles, and demo users if they don't exist."""
    async with AsyncSessionLocal() as db:
        # Check if data already exists
        hospital_count = (await db.execute(select(Hospital))).scalars().all()
        if hospital_count and len(hospital_count) > 0:
            print("⏭️  Demo data already exists, skipping seed")
            return

        # Seed hospitals
        for h in HOSPITALS:
            hospital = Hospital(**h)
            db.add(hospital)

        await db.flush()

        # Seed users (drivers)
        drivers_dict = {}
        for v in VEHICLES:
            driver_name = v["driver_name"]
            driver_phone = v["driver_phone"]
            
            # Check if driver exists
            driver_stmt = select(User).where(User.phone == driver_phone)
            driver = (await db.execute(driver_stmt)).scalar_one_or_none()
            
            if not driver:
                driver = User(
                    name=driver_name,
                    phone=driver_phone,
                    role=UserRole.DRIVER,
                    hashed_password="demo1234"
                )
                db.add(driver)
                await db.flush()
            
            drivers_dict[driver_phone] = driver.id

        # Seed demo users
        for u in DEMO_USERS:
            user_stmt = select(User).where(User.email == u["email"])
            user = (await db.execute(user_stmt)).scalar_one_or_none()
            
            if not user:
                user = User(
                    name=u["name"],
                    phone=u["phone"],
                    email=u["email"],
                    role=u["role"],
                    hashed_password=u["hashed_password"]
                )
                db.add(user)
                await db.flush()

        # Seed vehicles
        for v in VEHICLES:
            vehicle_stmt = select(Vehicle).where(Vehicle.registration == v["registration"])
            vehicle = (await db.execute(vehicle_stmt)).scalar_one_or_none()
            
            if not vehicle:
                vehicle = Vehicle(
                    registration=v["registration"],
                    tier=v["tier"],
                    current_lat=v["lat"],
                    current_lng=v["lng"],
                    driver_id=drivers_dict.get(v["driver_phone"])
                )
                db.add(vehicle)

        await db.commit()
        print(f"✅ Seeded {len(HOSPITALS)} hospitals, {len(VEHICLES)} vehicles, {len(DEMO_USERS)} demo users")
