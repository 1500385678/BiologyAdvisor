"""BiologyAdvisor · FastAPI 最小骨架

Phase 0 收尾期(2026-09-04)启动,只为 Phase 1 提供 repo 入口与可运行工程信号。

当前路由:
- GET /            → 根路径,返回项目元信息
- GET /health      → 健康检查(用于容器探针 / 部署验证)
- GET /version     → 版本号(来自 app.__init__.__version__)
- GET /api/v1/info → Phase 1 路由占位,返回 v1 命名空间预留说明

不做什么(明确边界,避免 Phase 0 过度工程化):
- 不连接 Neo4j / Milvus / PostgreSQL(Phase 1 ETL 子项按需引入)
- 不实现任何生物业务接口(留给 Phase 1 MVP)
- 不引入鉴权 / CORS 中间件(Phase 2)
- 不打 Docker 镜像(Phase 1 部署子项)
"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__

app = FastAPI(
    title="BiologyAdvisor",
    description="17-生物-Biology 行业 Web · 最小可运行骨架",
    version=__version__,
)


@app.get("/")
def root() -> dict:
    """根路径 · 项目元信息"""
    return {
        "project": "BiologyAdvisor",
        "internal_code": "17-生物-Biology",
        "version": __version__,
        "phase": "Phase 0 收尾期 → Phase 1 准备",
        "docs": {
            "plan": "项目开发计划.md",
            "architecture": "docs/architecture/",
            "queries": "docs/queries/",
        },
    }


@app.get("/health")
def health() -> dict:
    """健康检查 · 用于部署探针"""
    return {"status": "ok", "version": __version__}


@app.get("/version")
def version() -> dict:
    """版本号"""
    return {"version": __version__}


@app.get("/api/v1/info")
def api_v1_info() -> JSONResponse:
    """Phase 1 路由占位 · 明确 v1 命名空间将承载的核心模块"""
    return JSONResponse(
        status_code=200,
        content={
            "namespace": "api/v1",
            "status": "reserved",
            "planned_modules": [
                "graph     — 知识图谱查询(Phase 1 第 2 项)",
                "species   — 物种库检索(Phase 1 第 4 项)",
                "anim      — 过程动画配置(Phase 1 第 4 项)",
                "ai        — AI 三件套讲解(Phase 1 第 3 项 + Phase 3)",
                "user      — 用户/进度/错题(Phase 2)",
            ],
            "note": "占位接口,Phase 1 子项启动时替换为真实实现",
        },
    )
