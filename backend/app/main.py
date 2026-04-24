import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.services.storm_warning import get_storm_warning_service

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="FastAPI scaffold for the MetaGuard hackathon project.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.on_event("startup")
async def startup_event() -> None:
    # 1. Start schema water
    await get_storm_warning_service().start_watcher()
    
    # 2. Pre-warm passport cache for top demo assets (Fire & Forget)
    from app.services.passport import DataPassportService
    demo_assets = [
        "warehouse.commerce.curated.fct_orders",
        "warehouse.commerce.curated.customer_360",
        "warehouse.commerce.raw.orders_archive"
    ]
    service = DataPassportService()
    for fqn in demo_assets:
        asyncio.create_task(asyncio.to_thread(service.get_passport, fqn))


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await get_storm_warning_service().stop_watcher()


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {"message": "MetaGuard backend is running."}
