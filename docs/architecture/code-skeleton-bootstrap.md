# 最小可运行代码骨架说明

> **项目**:BiologyAdvisor · 17-生物 · Phase 0 收尾期交付物
> **版本**:v0.1.0-skeleton · 2026-09-04
> **状态**:可运行 · 仅工程信号,不含业务逻辑
> **触发建议**:T1 巡检(2026-09-04 02:41,commit `39b3aba`)T5 建议"连续 2 天"

---

## 1. 为什么需要这个骨架

Phase 0 已 5/7 主项 + 3 子节点闭合,但"连续 10 天源代码 0 文件"让 Phase 1 4-6 周工期表的工程起点缺失。Phase 0 截止 09-06 还剩 2 天,在最后窗口先建立一个**可运行 hello world** 骨架,把"工程信号"从 0 推到 1,Phase 1 子项可以基于此 repo 入口直接推进。

---

## 2. 骨架结构

```
BiologyWeb/
├── app/                    ← 新增 · FastAPI 包
│   ├── __init__.py         ← 包标记,__version__ = "0.1.0-skeleton"
│   └── main.py             ← FastAPI app 实例 + 4 个最小路由
├── requirements.txt        ← 新增 · 最小依赖(FastAPI + uvicorn + pydantic)
├── docs/
│   └── architecture/
│       └── code-skeleton-bootstrap.md  ← 本文档
├── 项目开发计划.md
├── 生物顾问开发架构与计划.md
└── README.md
```

---

## 3. 启动步骤

### 3.1 本地开发

```bash
cd /Users/aaron/Mac/Consultant/17-生物-Biology/_BiologyLib/BiologyWeb

# 1. 装依赖(建议 venv,但骨架极简,系统 pip 也可)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 启动开发服务器
python -m uvicorn app.main:app --reload --port 8000

# 3. 验证
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0-skeleton"}

curl http://localhost:8000/
# → {"project":"BiologyAdvisor", ...}
```

### 3.2 OpenAPI 文档

启动后访问:

- Swagger UI:http://localhost:8000/docs
- ReDoc:http://localhost:8000/redoc
- OpenAPI JSON:http://localhost:8000/openapi.json

---

## 4. 路由清单(当前 4 个)

| Method | Path | 用途 | 后续演进 |
|---|---|---|---|
| GET | `/` | 项目元信息 | 保留(可扩展为前端 SPA 入口) |
| GET | `/health` | 健康检查 | 容器探针(K8s livenessProbe) |
| GET | `/version` | 版本号 | 发版管理(deployment 标签) |
| GET | `/api/v1/info` | v1 命名空间占位 | Phase 1 子项替换为真实业务路由 |

**保留扩展点**:`/api/v1/{graph,species,anim,ai,user}` —— 命名已在 `main.py` 的 `planned_modules` 字段声明,Phase 1 启动时直接 `app.include_router(...)` 接入。

---

## 5. Phase 1 接入点(给后续子项的"接力棒")

| Phase 1 子项 | 接入位置 | 依赖 |
|---|---|---|
| 5 个核心数据源 ETL | `app/services/etl/{ncbi,uniprot,ensembl,clinicaltrials,chembl}.py` | requests + 各源 API Key(09-05 节点获取) |
| Neo4j 图谱 | `app/services/graph_engine.py` + `app/api/graph.py` | neo4j-python-driver,接 `/api/v1/graph` |
| LangGraph Agent | `app/services/ai_tutor.py` + `app/api/ai.py` | langgraph + LLM SDK(已锁 Claude Sonnet 4 / Gemini 2.5 Pro,见 llm-selection-eval.md) |
| PubMed RAG → Milvus | `app/services/pubmed_rag.py` + `app/api/ai.py` | pymilvus + sentence-transformers |
| 飞书 Agent 内测 | 独立进程,读 FastAPI `/api/v1/ai/*` | lark-oapi + 当前已部署的飞书通道 |
| Web App 最小版 | Next.js(独立前端仓库),读 FastAPI `/api/v1/*` | 与本骨架解耦,通过 HTTP 对接 |

---

## 6. 不做什么(明确边界)

- **不**连接任何数据库 / 缓存 / 图谱(避免 Phase 0 过度工程化)
- **不**实现业务接口(留给 Phase 1 子项)
- **不**引入鉴权 / CORS / 限流中间件(Phase 2)
- **不**打 Docker 镜像 / K8s manifest(Phase 1 部署子项)
- **不**写测试代码(Phase 1 第一个子项再加 pytest)
- **不**改 §5 已有未完成项(API Key 真申请 09-05 节点,需张勇本人登录邮箱)

---

## 7. 变更记录

| 日期 | commit | 动作 |
|---|---|---|
| 2026-09-04 | (本次) | 新建 app/ + requirements.txt + 本文档,§5 新增并勾选"启动最小可运行代码骨架"checkbox |
