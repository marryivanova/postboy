from os import path

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse
from loguru import logger

from settings import settings
from src.api import api_router
from src.api.endpoints.auth import verify_credentials

debug_log_path = path.join(path.dirname(__file__), "logs", "debug", "logs.log")
logger.add(
    debug_log_path,
    format="|n| {time:YYYY-MM-DD HH:mm:ss} || {level} || {message}",
    level="DEBUG",
    rotation="00:00",
    retention="30 days",
    compression="zip",
)

info_log_path = path.join(path.dirname(__file__), "logs", "info", "logs.log")
logger.add(
    info_log_path,
    format="{time:YYYY-MM-DD HH:mm:ss} || {message}",
    level="INFO",
    rotation="00:00",
    retention="30 days",
    compression="zip",
)

app = FastAPI(
    title="MAILMAN",
    description="""
    ## Общее описание

    **MAILMAN** - Массовый рассылщик рекламы **API MAX + TG**, 
    предназначенный для автоматизации бизнес-процессов и бесшовной интеграции 
    с экосистемой **Битрикс24 (BX24)**.
    """,
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.environment != "PROD" else None,
)


@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(verify_credentials)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="Docs")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(verify_credentials)):
    return get_redoc_html(openapi_url="/openapi.json", title="ReDoc")


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Hello World", "status": "ok"}


app.include_router(api_router)

if __name__ == "__main__":
    logger.info(f"Запуск сервера на {settings.app.host}:{settings.app.port}")

    uvicorn.run(
        "main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.environment == "DEV",
        log_level="info" if settings.environment == "PROD" else "debug",
        access_log=False,
    )
