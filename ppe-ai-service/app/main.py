from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="面向 PPE 营销物料自动生成系统的独立 AI 服务。当前版本用于接口联调和 AI 能力逐步接入。",
)

app.include_router(router)


@app.get("/health", summary="健康检查", tags=["系统状态"])
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
