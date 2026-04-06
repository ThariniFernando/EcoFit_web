import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routers.alerts_router import router as alerts_router
from routers.complaints_router import router as complaints_router
from routers.dispatch_router import router as dispatch_router
from routers.ml_router import router as ml_router
from routers.municipality_router import router as municipality_router
from routers.operations_router import router as operations_router
from routers.predictions_router import router as predictions_router
from routers.service_logs_router import router as service_logs_router
from routers.ward_hourly_features_router import router as ward_hourly_features_router
from routers.wards_router import router as wards_router
from routers.weather_hourly_router import router as weather_hourly_router
from routers.auth_router import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [k for k in ("MONGO_URL", "DB_NAME", "JWT_SECRET") if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {missing}")

    from database import client
    await client.admin.command("ping")
    print("✅ MongoDB connected")

    yield

    client.close()
    print("✅ MongoDB connection closed")


app = FastAPI(title="EcoFit Municipal API", lifespan=lifespan)

_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
cors_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(alerts_router)
app.include_router(complaints_router)
app.include_router(dispatch_router)
app.include_router(ml_router)
app.include_router(municipality_router)
app.include_router(operations_router)
app.include_router(predictions_router)
app.include_router(service_logs_router)
app.include_router(ward_hourly_features_router)
app.include_router(wards_router)
app.include_router(weather_hourly_router)
app.include_router(auth_router)


@app.get("/")
def root():
    return {"status": "ok"}