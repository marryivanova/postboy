from fastapi import APIRouter, Depends

from src.api.endpoints import auth, sender, sender_mock, updater, validate

api_router = APIRouter(prefix="/v1")

api_router.include_router(sender.router)
api_router.include_router(updater.router)
api_router.include_router(sender_mock.router)

api_router.include_router(validate.router)
