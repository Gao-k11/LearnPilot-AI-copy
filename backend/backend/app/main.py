import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.api.profile_builder import router as profile_builder_router
from backend.app.api.profile import router as profile_router
from backend.app.api.producer import router as producer_router
from backend.app.api.path import router as path_router
from backend.app.api.ml import router as ml_router
from backend.app.api.resources import router as resources_router
from backend.app.core.config import get_settings
from backend.app.core.database import (
    Base,
    engine,
    ensure_course_resource_columns,
    ensure_learning_path_columns,
    ensure_ml_profile_answer_columns,
    ensure_producer_columns,
    ensure_resource_center_columns,
    ensure_student_profile_columns,
)

settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("learnpilot.backend")

app = FastAPI(
    title=settings.app_name,
    description="基于大模型的个性化资源生成与学习多智能体系统后端",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(resources_router)
app.include_router(profile_builder_router)
app.include_router(producer_router)
app.include_router(profile_router)
app.include_router(path_router)
app.include_router(ml_router)

try:
    Base.metadata.create_all(bind=engine)
    ensure_student_profile_columns()
    ensure_course_resource_columns()
    ensure_resource_center_columns()
    ensure_producer_columns()
    ensure_learning_path_columns()
    ensure_ml_profile_answer_columns()
except Exception:
    logger.exception("database schema initialization failed")
    raise


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception("request failed", extra={"request_id": request_id})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": str(exc), "request_id": request_id}},
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.4f}"
    logger.info("%s %s %s", request.method, request.url.path, response.status_code)
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=settings.app_port, reload=True)
