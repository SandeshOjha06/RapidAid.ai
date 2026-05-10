from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.core.config import settings
from app.routers.routers import (
    health_router, emergency_router, hospital_router, 
    vehicle_router, dashboard_router, ws_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown."""
    # STARTUP
    await init_db()
    
    if settings.DEMO_MODE:
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from data_simulation.seed import seed_demo_data
            await seed_demo_data()
            print("✅ Demo data seeded")
        except Exception as e:
            print(f"⚠️  Could not seed demo data: {e}")
    
    print(f"🚀 {settings.APP_NAME} started on http://localhost:8000")
    print(f"📚 Swagger UI: http://localhost:8000/docs")
    print(f"🔧 ReDoc: http://localhost:8000/redoc")
    
    yield
    
    # SHUTDOWN
    print(f"🛑 {settings.APP_NAME} shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Multi-Agent Emergency Medical Response Ecosystem",
    lifespan=lifespan
)

# CORS Middleware — REQUIRED for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Mount routers
app.include_router(health_router)
app.include_router(emergency_router)
app.include_router(hospital_router)
app.include_router(vehicle_router)
app.include_router(dashboard_router)
app.include_router(ws_router)  # WebSocket routes


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
