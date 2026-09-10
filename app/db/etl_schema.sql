-- =============================================================================
-- BiologyAdvisor · ETL 状态表 DDL v1
-- =============================================================================
-- 项目:        BiologyAdvisor · 17-生物-Biology 行业 Web
-- 节点:        Phase 0 收尾延长期 cron T4 任务(2026-09-11)
-- 来源:        docs/architecture/etl-incremental-sync-design.md §3 / §7
-- 用途:        闭合 etl-incremental-sync-design.md §10 Phase 1 9 项验收 checklist
--              第 1 项"etl_state / etl_run_log / etl_quarantine 三表在 PostgreSQL
--              落地,索引齐全"的 DDL 文件前置入库
-- 依赖:        PostgreSQL 14+(BIGSERIAL / JSONB / 部分索引)
-- 不依赖:      NCBI API Key · Neo4j · Milvus(纯 PostgreSQL DDL,Phase 1 实施期再上线)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. etl_state · ETL 状态总览(每数据源 1 行)
-- -----------------------------------------------------------------------------
-- 来源:etl-incremental-sync-design.md §3
-- 用途:每数据源(NCBI Gene / UniProt / Ensembl / ClinicalTrials)的
--      "上次全量 / 上次增量 / release 标识 / md5 / 状态"总览
-- 互斥:启动前 UPDATE status='running' 受影响行数 = 1 才能继续
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_state (
    source              VARCHAR(32)  PRIMARY KEY,            -- 'ncbi_gene' / 'uniprot' / 'ensembl' / 'clinicaltrials'
    last_full_sync      TIMESTAMP   NOT NULL,                 -- 上次全量完成时间
    last_incr_sync      TIMESTAMP,                            -- 上次增量完成时间(NULL = 从未跑过增量)
    last_release        VARCHAR(64),                          -- 上次同步 release(UniProt '2026_03' / Ensembl '113' / NCBI 'daily-2026-09-09')
    record_count        BIGINT,                               -- 当前最新条目数
    last_md5            VARCHAR(64),                          -- 上次 dump md5(增量 patch 校验用)
    next_run_due        TIMESTAMP,                            -- 下次应跑时间(cron 判定)
    status              VARCHAR(16)  NOT NULL DEFAULT 'idle', -- 'idle' / 'running' / 'failed' / 'paused'
    last_error          TEXT,                                 -- 上次失败原因
    last_run_id         BIGINT,                               -- 关联 etl_run_log.id
    created_at          TIMESTAMP   NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT now()
);

-- status 索引(失败告警扫表用)
CREATE INDEX IF NOT EXISTS etl_state_status_idx
    ON etl_state(status);

-- next_run_due 部分索引(只覆盖 idle 状态的"待跑"行,扫表开销小)
CREATE INDEX IF NOT EXISTS etl_state_next_run_idx
    ON etl_state(next_run_due)
    WHERE status = 'idle';


-- -----------------------------------------------------------------------------
-- 2. etl_run_log · 每次 ETL 跑一行
-- -----------------------------------------------------------------------------
-- 来源:etl-incremental-sync-design.md §7.1
-- 用途:dashboard 查"最近一次 NCBI Gene 增量跑了多久 / 加载多少条 / 失败多少条"
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_run_log (
    id              BIGSERIAL    PRIMARY KEY,
    source          VARCHAR(32)  NOT NULL,                       -- 'ncbi_gene' / 'uniprot' / 'ensembl' / 'clinicaltrials'
    run_type        VARCHAR(16)  NOT NULL,                       -- 'full' / 'incremental'
    started_at      TIMESTAMP    NOT NULL,
    finished_at     TIMESTAMP,
    status          VARCHAR(16)  NOT NULL DEFAULT 'running',     -- 'running' / 'success' / 'failed' / 'partial'
    records_loaded  BIGINT,
    records_failed  BIGINT,
    md5_verified    BOOLEAN,
    duration_sec    INTEGER,
    error_message   TEXT
);

-- 复合索引:按 source + started_at DESC 查"该源最近一次跑"
CREATE INDEX IF NOT EXISTS etl_run_log_source_idx
    ON etl_run_log(source, started_at DESC);


-- -----------------------------------------------------------------------------
-- 3. etl_quarantine · 隔离失败记录(不阻塞主流程)
-- -----------------------------------------------------------------------------
-- 来源:etl-incremental-sync-design.md §7.2
-- 用途:Pydantic validation 失败的记录入此,人工 review
-- 阈值:resolved=FALSE 比例 < 1% 正常,1-5% 黄,> 5% 红(暂停增量)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_quarantine (
    id              BIGSERIAL    PRIMARY KEY,
    run_id          BIGINT       REFERENCES etl_run_log(id) ON DELETE CASCADE,
    source          VARCHAR(32)  NOT NULL,
    raw_record      JSONB,                                       -- 原始记录原文
    error_reason    TEXT,                                        -- Pydantic validation 失败原因
    quarantined_at  TIMESTAMP    NOT NULL DEFAULT now(),
    resolved        BOOLEAN      NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMP
);

-- 待 review 索引(resolved=FALSE 扫表)
CREATE INDEX IF NOT EXISTS etl_quarantine_pending_idx
    ON etl_quarantine(quarantined_at)
    WHERE resolved = FALSE;

-- 关联 run 索引
CREATE INDEX IF NOT EXISTS etl_quarantine_run_idx
    ON etl_quarantine(run_id);


-- =============================================================================
-- 元数据
-- =============================================================================
-- 节点耗时:     1 次 cron T4 窗口(纯 DDL 编写,无实际 PostgreSQL 连接)
-- 关联文档:     [[../docs/architecture/etl-incremental-sync-design.md]]
-- 关联任务:     [[../项目开发计划.md]] §6 Phase 1 第 1 项
-- 不做什么:
--   - ❌ 不在本文件写 INSERT(种子数据由 ETL 真实跑产出)
--   - ❌ 不在 etl_state 加 trigger(updated_at 自动维护留 Phase 1 实施期)
--   - ❌ 不连 Neo4j(Neo4j 索引/约束见 [[../docs/architecture/neo4j-schema-v1.md]])
--   - ❌ 不引 Alembic 迁移工具(Phase 1 决策)
-- 下一步:      Phase 1 实施期(预计 9-13 ~ 9-25)用 `psql -f app/db/etl_schema.sql`
--              把本文件落地到 PostgreSQL 14+,然后跑 etl 真实 ETL 写入
-- =============================================================================
