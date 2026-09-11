# BiologyAdvisor · app/db 目录说明

> Phase 1 ETL 实施期的 PostgreSQL DDL 集中目录
> 创建节点:2026-09-12(cron T5 跟 9-11 `e10e779` 落地 `etl_schema.sql` 配套)

---

## 1. 文件清单

| 文件 | 作用 | 状态 |
|---|---|---|
| `__init__.py` | 子包占位 + 模块说明(不放 ORM 代码) | 已落地(9-11) |
| `etl_schema.sql` | etl_state / etl_run_log / etl_quarantine 三表 DDL + 索引/外键/CHECK 约束 | 已落地(9-11 `e10e779`) |

`etl_schema.sql` 来源:`docs/architecture/etl-incremental-sync-design.md` §3(etl_state)/ §7.1(etl_run_log)/ §7.2(etl_quarantine)

---

## 2. 快速应用

### 2.1 前置条件

- PostgreSQL **14+**(依赖 `BIGSERIAL` / `JSONB` / 部分索引)
- 已创建空数据库(如 `biologyadvisor`)
- 已配置 `DATABASE_URL` 环境变量(或使用 psql 命令行直接传参)

### 2.2 一行命令应用(开发环境)

```bash
# 方式 A · psql 命令行直传(本地开发,无需 .env)
psql "postgresql://biology:biology@localhost:5432/biologyadvisor" \
     -v ON_ERROR_STOP=1 \
     -f app/db/etl_schema.sql

# 方式 B · 从环境变量读 DATABASE_URL(Phase 1 实施期推荐)
export DATABASE_URL="postgresql://biology:biology@localhost:5432/biologyadvisor"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f app/db/etl_schema.sql
```

**关键开关**:`-v ON_ERROR_STOP=1` —— 任一语句失败立即中断,避免半套 DDL 落库。

### 2.3 Idempotent 保护

`etl_schema.sql` 全部使用 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS`,可重复执行不会报错。Phase 1 实施期每次环境初始化可直接跑,无需维护 schema 版本号(若引入 alembic 则改走迁移工具链,见 §5)。

---

## 3. 三表说明

### 3.1 `etl_state` · ETL 状态总览(每数据源 1 行)

**作用**:每数据源(NCBI Gene / UniProt / Ensembl / ClinicalTrials)一行,记录"上次全量 / 上次增量 / release 标识 / md5 / 状态"。

**11 列**:

| 列 | 类型 | 说明 |
|---|---|---|
| `source` | VARCHAR(32) PK | `'ncbi_gene'` / `'uniprot'` / `'ensembl'` / `'clinicaltrials'` |
| `last_full_sync` | TIMESTAMP | 上次全量完成时间(NOT NULL) |
| `last_incr_sync` | TIMESTAMP | 上次增量完成时间(NULL = 从未跑过增量) |
| `last_release` | VARCHAR(64) | 上次同步 release,如 UniProt `2026_03` / Ensembl `113` / NCBI `daily-2026-09-09` |
| `record_count` | BIGINT | 当前最新条目数 |
| `last_md5` | VARCHAR(64) | 上次 dump md5(增量 patch 校验用) |
| `next_run_due` | TIMESTAMP | 下次应跑时间(cron 判定) |
| `status` | VARCHAR(16) | `'idle'` / `'running'` / `'failed'` / `'paused'` |
| `last_error` | TEXT | 上次失败原因 |
| `last_run_id` | BIGINT | 关联 `etl_run_log.id` |
| `created_at` / `updated_at` | TIMESTAMP | 行级时间戳 |

**互斥约束**:启动前 `UPDATE status='running'` 受影响行数 = 1 才能继续(防止并发跑同一源)。

### 3.2 `etl_run_log` · 每次 ETL 跑一行

**作用**:dashboard 查"最近一次 NCBI Gene 增量跑了多久 / 加载多少条 / 失败多少条"。

**关键列**:`id`(BIGSERIAL PK)/ `source` / `run_type`(`'full'` / `'incremental'`)/ `started_at` / `finished_at` / `status` / `records_loaded` / `records_failed` / `md5_verified` / `duration_sec` / `error_message`

**复合索引**:`(source, started_at DESC)` —— 查"该源最近一次跑"走索引扫描。

### 3.3 `etl_quarantine` · 隔离失败记录(不阻塞主流程)

**作用**:Pydantic validation 失败的记录入此表,人工 review。**不阻塞主流程**(不等 quarantine 清空就继续跑下一次)。

**关键列**:`id`(BIGSERIAL PK)/ `run_id`(外键 `etl_run_log.id` ON DELETE CASCADE)/ `source` / `raw_record`(JSONB 原文)/ `error_reason` / `quarantined_at` / `resolved`(BOOLEAN)/ `resolved_at`

**告警阈值**:`resolved=FALSE` 比例 < 1% 正常,1-5% 黄,> 5% 红(暂停增量)。

---

## 4. 验证查询(smoke test)

应用完 DDL 后,跑以下 4 条查询确认三表结构 + 索引齐全:

```sql
-- ① 三表都已建
SELECT tablename FROM pg_tables
 WHERE schemaname = 'public'
   AND tablename IN ('etl_state', 'etl_run_log', 'etl_quarantine');
-- 期望:3 行

-- ② etl_state 主键 + 索引齐
SELECT indexname FROM pg_indexes
 WHERE tablename = 'etl_state'
 ORDER BY indexname;
-- 期望:etl_state_pkey + etl_state_status_idx + etl_state_next_run_idx = 3 行

-- ③ etl_run_log 复合索引存在
SELECT indexdef FROM pg_indexes
 WHERE indexname = 'etl_run_log_source_idx';
-- 期望:命中 (source, started_at DESC) 索引定义

-- ④ etl_quarantine 外键 + 部分索引
SELECT conname, contype FROM pg_constraint
 WHERE conrelid = 'etl_quarantine'::regclass;
-- 期望:etl_quarantine_pkey + etl_quarantine_run_id_fkey(外键) = 2 行
```

**Phase 1 实施期建议**:把上述 4 条查询封装为 `scripts/verify_db_schema.py`,跑通后输出 "etl_schema.sql 已就位" 信号(参考已闭合的 `scripts/verify_ncbi_key.py` / `verify_clinicaltrials.py` 模式)。

---

## 5. 迁移工具链(占位段,Phase 1 启动前再决议)

**当前状态**:**不引入 Alembic**。`etl_schema.sql` 是裸 SQL,Phase 1 ETL 启动前再决议是否引入迁移工具。

**决策点**(Phase 1 启动日 9-13 ~ 9-15 评估):

| 选项 | 适用场景 | 反对场景 |
|---|---|---|
| 维持裸 SQL(`psql -f`) | 表结构稳定期,DDL 变更 < 1 次/周 | 频繁改 schema 时手工维护成本高 |
| 引入 Alembic | 多人协作 + schema 频繁迭代 | 5 张表规模小,引入学习成本不划算 |

**决议前约定**(任选其一即可):

- 选项 A:继续裸 SQL,新增表 → 新建 `etl_schema_xxx.sql` 单文件,文档写明执行顺序
- 选项 B:引入 Alembic → 初始化 `alembic init app/db/migrations`,把 `etl_schema.sql` 翻译为 `001_init_etl.py` 迁移脚本

**截至 2026-09-12 立场**:**选项 A**(继续裸 SQL)。理由:Phase 1 头两周重点是 ETL 实跑,迁移工具链留到 Phase 1 末尾(预计 9-25 后)再评估,避免一次性引入太多新工具拖慢主线。

---

## 6. 不做什么

- ❌ **不写 ORM 封装**(SQLAlchemy 留 Phase 1 决策,etl_state / etl_run_log 直接走 raw SQL 写入)
- ❌ **不写连接池**(asyncpg / psycopg 留 Phase 1 实施期,本 README 不预设)
- ❌ **不写 DDL 自动化脚本**(无 `apply_ddl.sh` / `make db-init`,避免重复工具链;需要时直接 `psql -f` 即可)
- ❌ **不写种子数据**(INSERT 由 ETL 真实跑产出,不在 DDL 文件里塞)
- ❌ **不写 trigger**(`updated_at` 自动维护留 Phase 1 实施期,DDL 文件保持纯结构定义)

---

## 7. 关联文档

- `docs/architecture/etl-incremental-sync-design.md` · ETL 增量同步设计 v1.0(§3 / §7.1 / §7.2 来源)
- `docs/architecture/neo4j-schema-v1.md` · Neo4j 节点/关系 schema(本目录只管 PostgreSQL,Neo4j 单独管)
- `docs/architecture/datasource-dump-eval.md` · 4 数据源 dump 评估
- `docs/architecture/api-keys-checklist.md` · NCBI API Key 申请清单(影响 §3 etl_state 第 1 条 source 能否实跑)
- `项目开发计划.md` §6 Phase 1 第 1 项 · 5 ETL 流水线
- `.Log/巡检-生物-20260912.md` · 今日巡检,本 README 是 §3 第 6 项建议的产出

---

## 8. 元数据

- 节点耗时:本 README 编写 1 次 cron T5 窗口(纯文档)
- 关联 commit:`e10e779`(`app/db/etl_schema.sql` + `app/db/__init__.py` 落地,9-12 T4 cron)
- 关联 plan:`.plan/20260912.md`
- 下一步:Phase 1 实施期(预计 9-13 ~ 9-25)用 `psql -f app/db/etl_schema.sql` 落地 + 跑 §4 smoke test + 启动第 1 条 ETL(NCBI Gene,待 API Key 真申请完成)
