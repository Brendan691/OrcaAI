"""小鲸 OrcaAI v0.3.0 — FastAPI 主入口"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .core.database import init_db
from .api.routes import router as documents_router
from .api.auth import router as auth_router
from .api.files import router as files_router
from .api.teams import router as teams_router
from .api.generate import router as generate_router

# 以下功能已实现但暂挪到路线图(见 ROADMAP.md),默认不启用:
#   - api.search  联网搜索(依赖 SearXNG)
#   - api.wechat  微信公众号接入(依赖公网+已认证公众号)
# 需要时取消注释并注册即可,代码文件保留在仓库中。


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="小鲸 OrcaAI",
    description="AI 驱动的一站式海事知识管理工具 — 收集、整理、应用、分享",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)  # ① 文档收藏/问答/搜索/标签
app.include_router(auth_router)        # ④ 用户认证
app.include_router(files_router)       # ② 文件上传
app.include_router(teams_router)       # ⑤ 团队协作
app.include_router(generate_router)    # ③ AI 报告生成


@app.get("/")
async def root():
    return {
        "name": "小鲸 OrcaAI",
        "version": "0.3.0",
        "description": "AI 驱动的一站式海事知识管理工具",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.APP_DEBUG)
