import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import health_router, regulator_router
from app.config import regulator_settings
from app.database import db_manager
from app.grpc_server import serve_grpc
from app.middleware import CorrelationIdMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Запуск Matryoshka Regulator Service...")
    grpc_server = await serve_grpc(regulator_settings.grpc_port)
    yield
    logger.info("Остановка Matryoshka Regulator Service...")
    await grpc_server.stop(5)
    await db_manager.close()


app = FastAPI(
    title=regulator_settings.app_name,
    version="1.0.0",
    description="Ситуационный центр Минпромторга: нормативный аудит ПП РФ № 719, моделирование санкционных шоков и ИИ-генерация геополитических сценариев (OpenRouter)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=regulator_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationIdMiddleware)

app.include_router(health_router.router)
app.include_router(regulator_router.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=regulator_settings.rest_host,
        port=regulator_settings.rest_port,
        reload=regulator_settings.debug,
    )
