from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.traffic import router as traffic_router
from app.api.ml import router as ml_router
from app.api.simulation import router as simulation_router
from app.api.routing import router as routing_router
from app.api.alerts import router as alerts_router
from app.api.emergency import router as emergency_router
from app.api.signals import router as signals_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(traffic_router)
api_router.include_router(ml_router)
api_router.include_router(simulation_router)
api_router.include_router(routing_router)
api_router.include_router(alerts_router)
api_router.include_router(emergency_router)
api_router.include_router(signals_router)
