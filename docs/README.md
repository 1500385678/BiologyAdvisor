# BiologyAdvisor · 文档导航

> `docs/` 目录总索引 · 2026-09-16 cron T4 落地 · 跟随 Phase 0 → Phase 1 进度持续更新

本目录是 BiologyAdvisor 的"设计意图 + 决策记录"沉淀处。代码层文件(`app/` · `scripts/` · `config/`)只放最小可运行骨架,所有"为什么这么做"的说明都集中在 `docs/`。

---

## 1. 目录结构

```
docs/
├── README.md                        ← 本文件(目录入口)
├── architecture/                    ← 架构设计 + 评估决策
│   ├── neo4j-schema-v1.md
│   ├── datasource-dump-eval.md
│   ├── etl-incremental-sync-design.md
│   ├── api-keys-checklist.md
│   ├── llm-selection-eval.md
│   └── code-skeleton-bootstrap.md
└── queries/
    └── benchmark-questions.md
```

---

## 2. architecture/ · 架构文档(6 份)

| # | 文档 | 阶段 | 用途 | 关联 |
|---|---|---|---|---|
| 1 | [neo4j-schema-v1.md](architecture/neo4j-schema-v1.md) | Phase 0 | Neo4j 节点/关系 schema 定义,6 实体 + 8 类关系 + 索引约束 | Phase 1 图谱搭建入口 |
| 2 | [datasource-dump-eval.md](architecture/datasource-dump-eval.md) | Phase 0 | NCBI Gene / UniProt / Ensembl / ClinicalTrials 4 源 dump 评估 + ETL 草案 | Phase 1 §6 ETL 实跑输入 |
| 3 | [etl-incremental-sync-design.md](architecture/etl-incremental-sync-design.md) | Phase 1 启动期 | ETL 增量同步设计 v1.0(11 列 `etl_state` + 三库增量策略) | §8.3 5 TODO 9-10 闭合 |
| 4 | [api-keys-checklist.md](architecture/api-keys-checklist.md) | Phase 0 → Phase 1 | NCBI / Ensembl / ClinicalTrials API Key 申请清单 + verify 验证脚本 | §5 #4 待主人启动 |
| 5 | [llm-selection-eval.md](architecture/llm-selection-eval.md) | Phase 0 | LLM 选型方法论 + Claude Sonnet 4 vs Gemini 2.5 Pro 6 维评估 + 20 题评分卡 | Phase 1 Agent 编排选型输入 |
| 6 | [code-skeleton-bootstrap.md](architecture/code-skeleton-bootstrap.md) | Phase 0 收尾期 | `app/main.py` FastAPI 启动步骤 + Phase 1 接入点 | §5 #1 启动期工程信号 |

---

## 3. queries/ · 查询基准

| # | 文档 | 阶段 | 用途 | 关联 |
|---|---|---|---|---|
| 1 | [benchmark-questions.md](queries/benchmark-questions.md) | Phase 0 | 12 题 · 3 用户 × 3 难度 + Phase 1 验收门槛 | Phase 1 §7 50 题 benchmark 基线 |

---

## 4. 当前已闭合节点(2026-09-16 cron T4 快照)

### Phase 0 §5(7/8 闭合,1 待人工)

- [x] §5 #1 Inspiration 索引盘点(8-24)
- [x] §5 #2 README 合并标记清理(8-26)
- [x] §5 #3 Neo4j schema 设计(8-27)
- [x] §5 #4 部分完成(verify 脚本 + CT 骨架 + .gitignore 凭证屏蔽,**NCBI Key 真申请待主人**)
- [x] §5 #5 benchmark 12 题(8-28)
- [x] §5 #6 LLM 选型方法论(8-29,实际盲测延后)
- [x] §5 #7 dump 全量拉取评估(9-01 + 9-03 + 9-05 节点 §8.3 5 TODO 9-10 闭合)
- [x] §5 #8 代码骨架 `app/main.py` + `requirements.txt` + bootstrap 文档(9-04)
- [ ] §5 #4 主人动作补充:NCBI API Key 真申请 + verify 跑通

### Phase 1 §6 第 1 项启动信号(4/4,工程化骨架层 100%)

- [x] ETL 增量同步设计 v1.0(9-10 `2898693` 闭合 §8.3 5 TODO)
- [x] ETL 三表 DDL + 应用说明(9-11 `e10e779` + 9-12 `5abf832`)
- [x] ETL DDL dry-run 自检基线(9-14 `4a9ee2e` 落地 `scripts/etl_dryrun.py`)
- [x] README 顶层 DDL dry-run 入口(9-15 `e598b0e` 落地 `## 自检基线` 章节)

→ **差 4 步**:实跑 5 源 ETL / 增量同步 / 监控告警 / checkbox 勾选(Phase 1 实施期决议)

### 巡检信号(.Log/)

- 巡检报告:`.Log/巡检-生物-YYYYMMDD.md`(T1 02:40 自动产出)
- 巡检覆盖率:**20/20 天**(9-14 漏跑 1 次已恢复)

---

## 5. 文档维护约定

**写入原则**

- 所有"为什么这么做"的决策记录写进 `docs/architecture/`
- 运行时配置写代码层(`app/` / `scripts/` / `config/`),不在 docs/ 放运行命令
- 引用锚点用 `[§X.Y](file.md#X-Y)` 显式标记,Obsidian Graph 友好

**更新时机**

- 新决策落地 → 新增或更新 architecture/ 文档 + 更新本 README 表格
- Phase 0 收尾报告落地后,本 README §4 切换为"Phase 1 启动期"快照

**不做的事**

- ❌ 不复制 README.md 内容进来(README 是项目入口,本目录是文档入口,职责分开)
- ❌ 不在 docs/ 写 ETL 运行脚本(脚本归 `scripts/`)
- ❌ 不在 docs/ 放图片(SVG / PNG 用 `docs/assets/` 时再独立建)

---

## 6. 关联文件

- [`../项目开发计划.md`](../项目开发计划.md) · 项目总览 + Phase 0/1/2/3 里程碑
- [`../生物顾问开发架构与计划.md`](../生物顾问开发架构与计划.md) · 项目原始架构与规划
- [`../app/db/README.md`](../app/db/README.md) · ETL DDL 应用说明(代码层 README,与文档层 README 职责不同)
- [`../README.md`](../README.md) · 项目根入口,含"## 自检基线 · DDL dry-run"章节

---

## 7. 元数据

- **落地节点**: 2026-09-16 cron T4(连续 8 天 P0 催办 · 文档索引就位信号)
- **触发**: 9-16 巡检 P0 建议"docs 目录长期无入口 README,索引能力缺失"
- **关联 commit**: (本次 T5 commit)
- **不引入**: 不迁移工具链(alembic 评估仍按 `app/db/README.md` §5 选项 A,Phase 1 末尾再决议)
- **下一步**: Phase 0 收尾报告落地后,本 README §4 切换为"Phase 1 启动期"快照;Phase 1 §6 第 1 项 5 源 ETL 实跑启动时,本 README 新增"ETL 实跑进度"小节
