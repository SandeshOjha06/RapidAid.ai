# RapidAid.ai Backend Setup Guide

## Prerequisites

- **Python 3.10+**
- **PostgreSQL 14+**
- **pip** or **conda**

## Installation

### 1. PostgreSQL Setup (Ubuntu/Debian)

```bash
sudo apt install postgresql postgresql-contrib
sudo service postgresql start

# Create user and database
sudo -u postgres psql << EOF
CREATE USER rapidaid WITH PASSWORD 'rapidaid123';
CREATE DATABASE rapidaid_db OWNER rapidaid;
GRANT ALL PRIVILEGES ON DATABASE rapidaid_db TO rapidaid;
EOF
```

### 2. Python Environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env if using non-default PostgreSQL credentials
```

### 5. Initialize Database

```bash
python3 << EOF
from app.database import init_db
import asyncio
asyncio.run(init_db())
EOF
```

## Running the Backend

### Terminal 1: FastAPI Server

```bash
uvicorn app.main:app --reload --port 8000
```

You should see:
```
🚀 RapidAid.ai started on http://localhost:8000
📚 Swagger UI: http://localhost:8000/docs
🔧 ReDoc: http://localhost:8000/redoc
✅ Demo data seeded
```

### Terminal 2: GPS Simulator (Optional)

For "Ghost Ambulance" demo that moves ambulances in real-time:

```bash
python -m data_simulation.simulator
```

Watch ambulances move 8% closer to patients every 3 seconds.

## Testing the Backend

### Option 1: Swagger UI (Interactive)

Open: **http://localhost:8000/docs**

Click on endpoints to test them directly.

### Option 2: cURL

#### Check Health
```bash
curl http://localhost:8000/
```

#### Get Hospitals
```bash
curl http://localhost:8000/hospitals/
```

#### Trigger SOS (Cardiac Emergency)
```bash
curl -X POST http://localhost:8000/emergency/sos \
  -H "Content-Type: application/json" \
  -d '{
    "patient_lat": 27.7172,
    "patient_lng": 85.3240,
    "patient_address": "Thamel, Kathmandu",
    "description": "cardiac arrest, person unconscious, not breathing",
    "emergency_type": "CRITICAL_SOS",
    "patient_name": "Ram Bahadur Thapa",
    "patient_phone": "+977-9841234567"
  }'
```

Copy the returned `short_id` (e.g., `EMG-A3F9`).

#### Get Emergency Details
```bash
curl http://localhost:8000/emergency/EMG-A3F9
```

See all 4 agent decisions with reasoning.

#### Update Hospital Status
```bash
curl -X PATCH http://localhost:8000/hospitals/{hospital_id}/status \
  -H "Content-Type: application/json" \
  -d '{"icu_status": "FULL"}'
```

#### Update Vehicle Location
```bash
curl -X PATCH http://localhost:8000/vehicles/{vehicle_id}/location \
  -H "Content-Type: application/json" \
  -d '{"lat": 27.72, "lng": 85.33}'
```

#### Get Dashboard Stats
```bash
curl http://localhost:8000/dashboard/stats
```

### Option 3: Postman Collection

Import `RapidAid_Postman_Collection.json` into Postman and run requests.

## Troubleshooting

### PostgreSQL Connection Error
```
Error: could not translate host name "localhost" to address
```

**Fix:** Ensure PostgreSQL is running:
```bash
sudo service postgresql restart
```

### ModuleNotFoundError

**Fix:** Ensure virtual environment is activated:
```bash
source venv/bin/activate
```

### Port 8000 Already in Use

**Fix:** Use a different port:
```bash
uvicorn app.main:app --reload --port 8001
```

## Architecture Overview

```
POST /emergency/sos
    ↓
AgentPipeline.process_sos()
    ├─► [1] TriageAgent: Keywords → Severity + Category
    ├─► [2] HospitalAgent: Find best hospital
    ├─► [3] DispatchAgent: Find closest vehicle
    └─► [4] RouteAgent: Calculate ETA + fare
    ↓
DB COMMIT (atomic)
    ↓
WebSocket broadcasts:
    → Hospital: "INCOMING P1_CRITICAL"
    → Driver: "Emergency assigned"
```

## Key Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/emergency/sos` | Create emergency, run pipeline |
| GET | `/emergency/{id}` | Get emergency + agent decisions |
| PATCH | `/emergency/{id}/status` | Update status (ON_SCENE, ARRIVED, etc.) |
| GET | `/hospitals/` | List all hospitals |
| PATCH | `/hospitals/{id}/status` | Toggle ICU/ER status |
| GET | `/vehicles/` | List all vehicles |
| PATCH | `/vehicles/{id}/location` | Driver GPS ping |
| GET | `/dashboard/stats` | Live dashboard numbers |
| WS | `/ws/patient/{id}` | Patient tracking channel |
| WS | `/ws/driver/{id}` | Driver assignment channel |
| WS | `/ws/hospital/{id}` | Hospital alert channel |

## Environment Variables

See `.env.example` for all options:
- `DATABASE_URL`: PostgreSQL async connection string
- `ALLOWED_ORIGINS`: CORS whitelist (for Next.js on port 3000)
- `DEMO_MODE`: Auto-seed demo data on startup
- `DEBUG`: Enable SQLAlchemy echo + Uvicorn reload

## Next Steps

- Set up Next.js frontend (see main README)
- Deploy to production (change SECRET_KEY, DEBUG=False)
- Implement YOLO11 image processing (Phase 2)
- Add OTP authentication
