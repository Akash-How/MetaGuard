from fastapi import APIRouter

from app.api.routes import blast_radius, chat, dead_data, health, passport, rca, storm_warning

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(dead_data.router, prefix="/dead-data", tags=["dead-data"])
api_router.include_router(passport.router, prefix="/passport", tags=["passport"])
api_router.include_router(storm_warning.router, prefix="/storm", tags=["storm"])
api_router.include_router(blast_radius.router, prefix="/blast-radius", tags=["blast-radius"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(rca.router, prefix="/rca", tags=["rca"])
