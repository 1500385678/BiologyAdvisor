# ETL 增量同步方案设计 v1

> 项目:BiologyAdvisor · 17-生物 · Phase 1 §6 第 1 项前置设计
> 版本:v1.0 · 2026-09-10
> 状态:设计稿(桌面研究,无代码),Phase 1 启动前最后一次桌面评审
> 上游:`docs/architecture/datasource-dump-eval.md` §10.5 增量同步钩子 + `api-keys-checklist.md` 凭证基线
> 下游:Phase 1 ETL 流水线实现(预计 9-13 ~ 9-25,本节点不写代码)

---

## 1. 方案目的

§10.5 已为 09-05 节点定义了 `etl_state` 表的最小契约,本节点在此基础上**完成三个数据源的增量同步策略**:
- 给出每个数据源的"上次全量时间戳"和"上次增量时间戳"如何驱动下次拉取
- 给出**增量 SQL 模板**或文件级 diff 协议
- 给出**跨库 ID 对齐的增量一致性**保证(UniProt 增量时如何保持 GeneID 关联稳定)
- 给出**调度窗口 / 失败重试 / 监控信号**的全套边界条件
- 给出 Phase 1 实施的 9 项验收 checklist

**核心结论**:Phase 1 增量策略 = "**全量打底 + 增量补齐 + 跨库对账**" 三段叠加,不靠单一增量路径。

---

## 2. 设计原则

1. **全量先行**:Phase 1 第一次跑必全量入 Neo4j(建立基线),之后才允许走增量
2. **增量必须有 WHERE 锚点**:NCBI 用 `Modification_date`,UniProt 用 `diff/` 目录,Ensembl 用 `release_version` 切换;**没有 WHERE 锚点的数据源禁止走增量**(避免漏数据)
3. **跨库 ID 不动**:增量同步只增/改节点属性,**禁止在增量阶段重写 GeneID 映射**(避免下游查询结果抖动)
4. **可重入**:增量失败后重跑不会产生重复节点(`MERGE` + 唯一约束)
5. **可回滚**:每次全量入库前对 Neo4j 做 snapshot,失败可回退到上一个稳定状态
6. **可观测**:每次 ETL 跑都写 `etl_run_log` 一行,失败写入 `etl_quarantine`,监控从这两张表读

---

## 3. etl_state 状态表(扩展 §10.5 最小契约)

§10.5 已定义最小契约(5 列),本节点扩展到 **11 列** 满足增量同步:

```sql
CREATE TABLE etl_state (
    source              VARCHAR(32)  PRIMARY KEY,   -- 'ncbi_gene' / 'uniprot' / 'ensembl' / 'clinicaltrials'
    last_full_sync      TIMESTAMP   NOT NULL,        -- 上次全量完成时间
    last_incr_sync      TIMESTAMP,                    -- 上次增量完成时间(NULL 表示从未跑过增量)
    last_release        VARCHAR(64),                  -- 上次同步的 release 标识(UniProt '2026_03' / Ensembl '113' / NCBI 'daily-2026-09-09')
    record_count        BIGINT,                       -- 当前最新条目数
    last_md5            VARCHAR(64),                  -- 上次 dump 的 md5(用于校验增量 patch)
    next_run_due        TIMESTAMP,                    -- 下次应跑时间(由 cron 判定)
    status              VARCHAR(16)  DEFAULT 'idle',  -- 'idle' / 'running' / 'failed' / 'paused'
    last_error          TEXT,                         -- 上次失败原因
    last_run_id         BIGINT,                       -- 关联 etl_run_log.id
    created_at          TIMESTAMP   NOT NULL DEFAULT now(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT now()
);

CREATE INDEX etl_state_status_idx ON etl_state(status);
CREATE INDEX etl_state_next_run_idx ON etl_state(next_run_due) WHERE status = 'idle';
```

**为什么扩展**:
- `last_release` — 增量触发时快速判断"新 release 是否已发布"(UniProt / Ensembl 这种固定周期释放的,增量逻辑就是"release 变了就拉 diff")
- `last_md5` — 增量下载时与官方校验和对比,若 md5 异常触发"重下全量"回退路径
- `status` — 防止并发跑(同 source 上一次没跑完下一次不能启动)
- `last_run_id` — 关联 `etl_run_log` 做全链路排错

---

## 4. 三库增量策略

### 4.1 NCBI Gene(日增量)

**释放周期**:每日更新(无固定版本号,只看 `Modification_date` 字段)

**Phase 1 增量方案**:
- **首次**:全量拉 `gene_info` + `gene2refseq` + `gene_history` + `gene2go` 4 文件,共 ~140 MB 压缩
- **之后**:每周日凌晨 03:00 跑增量(磁盘 + 解析开销 ~5-10 分钟)
- **增量锚点**:`gene_info.Modification_date > etl_state.last_incr_sync` AND `tax_id = 9606`
- **增量范围**:只拉人类(`tax_id=9606`),其他物种不进 Phase 1

**增量 SQL 模板**:
```sql
-- 用于"先查增量候选 ID,再批量拉详情"的两段式
-- 第一段:从 etl_state 读上次增量时间戳
SELECT last_incr_sync, last_full_sync
FROM etl_state WHERE source = 'ncbi_gene';

-- 第二段:用 last_incr_sync 过滤(实际 ETL 中用 Python read_csv + chunksize 流式)
-- pandas 等价:
-- df = pd.read_csv('gene_info.gz', sep='\t', chunksize=10000)
-- for chunk in df:
--     if chunk['Modification_date'].max() <= last_incr_sync: continue
--     human = chunk[chunk['tax_id'] == 9606]
--     yield human
```

**失败回退**:若增量阶段发现 `record_count` 较上次全量 `record_count` 减少 > 5%,自动触发"重新全量"安全网(防止 dump 文件被 NCBI 内部重写时漏掉条目)。

### 4.2 UniProt(8 周全量 + diff 增量)

**释放周期**:每 8 周一 release(明确版本号,如 `2026_03`)

**Phase 1 增量方案**:
- **首次**:全量拉 `human.dat` + `idmapping.dat.gz`,共 ~5 GB 压缩
- **8 周节点**:拉新 release 全量,**不用 diff**(版本跨度大,diff 累积反而比全量慢)
- **8 周窗口内**:每周一次拉 `diff/` 目录 patch(每 patch ~50-200 MB)

**Phase 1 增量锚点**:
```bash
# UniProt diff 目录示例
https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-2026_02/knowledgebase/complete/diff/
```

**8 周全量决策表**:

| 距上次全量(天) | 动作 | 数据量 |
|---|---|---|
| 0-7 | 仅 diff 增量 | ~50 MB |
| 8-14 | 仅 diff 增量 | ~100 MB |
| 15-49 | 仅 diff 增量(累积) | ~200 MB |
| 50-56 | **触发新 release 全量** | ~5 GB |
| 57+ | 触发全量 + 告警("8 周窗口严重超期") | ~5 GB + 红色日志 |

**为什么不全用 diff**:累积 6-7 周 diff 与全量同量级,但全量能"重新对齐" idmapping 跨表,避免增量跑 6 周后突然发现 idmapping 已变;**全量是天然的 checkpoint**。

### 4.3 Ensembl(4 月全量 + BioMart 增量)

**释放周期**:每 4 个月一 release(明确版本号,如 `release-113`)

**Phase 1 增量方案**:
- **首次**:全量拉 `Homo_sapiens.GRCh38.113.gtf.gz`(~30 MB)
- **4 月节点**:拉新 release 全量
- **4 月窗口内**:每 2 周用 Ensembl BioMart 拉 `new_transcripts`(仅新增转录本,Phase 1 可选,Phase 2 必选)

**Phase 1 增量锚点**:
```python
# BioMart 查询(伪代码)
new_transcripts = biomart.query(
    dataset='hsapiens_gene_ensembl',
    filters={'transcript_gencode_basic': 'OTTONLYNEW'},  # 仅新增
    attributes=['ensembl_gene_id', 'ensembl_transcript_id', 'chromosome_name', 'start_position', 'end_position']
)
```

**Phase 1 简化**:由于 Transcript 节点在 Phase 1 不入库(§10.1 矩阵标"Phase 1 暂只建 Gene 节点,Transcript 留 Phase 2"),Ensembl 在 Phase 1 只作"校核源"用,**4 月全量 + 2 周 BioMart 增量都是 P1(可选)**。

### 4.4 ClinicalTrials.gov(2 周增量,Phase 1 P1)

虽然不在 §10.5 三库内,但 §6 临床试验 ETL 是 Phase 1 §6 第 1 项的第 5 个数据源。**Phase 1 增量策略**:
- 首次:全量分页拉(每页 50 条,默认 `user_agent` 走 `config/clinicaltrials.yaml`)
- 之后:每 2 周一次,按 `last_update_post_date` 字段过滤
- **重要**:CT.gov v2 API 无固定 release 编号,只能按时间戳增量

**Phase 1 起步延期**:ClinicalTrials 实体入库在 Phase 2 启动,Phase 1 仅做"可达性 + 字段映射"探路,见 `verify_clinicaltrials.py` 实跑结果。

---

## 5. 跨库 ID 对齐的增量一致性

这是 §10.4 三步走策略的**增量一致性扩展**——增量阶段如何保证 UniProt ↔ NCBI GeneID 映射**不漂移**。

### 5.1 全量阶段(Phase 1 启动首跑)

按 §10.4 三步走:
1. **第一优先**:UniProt `dbReference type="GeneID"`(~95% 覆盖)
2. **第二兜底**:`idmapping.dat.gz` GeneID 列
3. **第三兜底**:symbol 反查 NCBI `gene_info`(`tax_id=9606` 过滤)

写入 Neo4j 时同时记录 `Protein.gene_id` 和 `Protein._alignment_method`(`direct` / `idmapping` / `symbol_lookup`),便于审计。

### 5.2 增量阶段(8 周内 diff 同步)

**核心纪律**:
- 增量阶段**只允许走第一步**(`dbReference` 字段直接读)
- **禁止**在增量阶段触发第二步(idmapping 重新加载)或第三步(symbol 反查)
- 若 diff 中某条记录的 `dbReference` 字段缺失,标记 `_alignment_method = 'pending'`,**留到下次全量对齐**

**为什么**:增量阶段频繁触发 idmapping 重新加载会导致:
- idmapping 表自身也在变,增量 vs idmapping 全量不一致
- 频繁跨库查询 QPS 风险(NCBI 10 req/s 限速)
- 失败回滚复杂度爆炸

**对齐率验收**:
- 全量阶段:对齐率目标 ≥ 95%(同 §10.4)
- 增量阶段:`_alignment_method = 'pending'` 比例目标 < 5%
- 若增量阶段 `pending` 累计 > 10%,**触发"提前全量"**安全网

---

## 6. 调度窗口(cron 时间表)

Phase 1 ETL 跑在每日凌晨窗口(避开用户活跃期 + NCBI 限速较宽松),所有 cron 任务互斥(同源不并发)。

| 任务 | cron 表达式 | 窗口 | 时长(估) | 互斥 |
|---|---|---|---|---|
| NCBI Gene 增量 | `0 3 * * 0` | 周日 03:00 | ~10 min | 与全量互斥 |
| NCBI Gene 全量 | `0 3 1 * *` | 每月 1 号 03:00 | ~30 min | 与增量互斥 |
| UniProt 增量(diff) | `0 4 * * 1` | 周一 04:00 | ~15 min | 与全量互斥 |
| UniProt 全量(8 周节点) | `0 4 1 1,3,5,7,9,11 *` | 1/3/5/7/9/11 月 1 号 04:00 | ~2 h(全量解压) | 与增量互斥 |
| Ensembl 增量(BioMart) | `0 5 * * 14` | 每月 14 号 05:00 | ~5 min | 与全量互斥 |
| Ensembl 全量(4 月节点) | `0 5 1 1,5,9 *` | 1/5/9 月 1 号 05:00 | ~20 min | 与增量互斥 |
| ClinicalTrials 增量 | `30 5 * * 14` | 每月 14 号 05:30 | ~30 min | — |

**互斥实现**:
- 启动前:`UPDATE etl_state SET status='running' WHERE source=? AND status='idle'` 受影响行数 = 1 才能继续
- 跑完:`UPDATE etl_state SET status='idle', updated_at=now() WHERE source=? AND status='running'`
- 失败:`UPDATE etl_state SET status='failed', last_error=? WHERE source=? AND status='running'`,触发告警飞书机器人

**窗口选择理由**:
- NCBI Gene 周日凌晨 03:00 — 周末用户最少 + NCBI 美东周六凌晨流量最低
- UniProt 周一 04:00 — 与 NCBI Gene 错开 1 h(避免磁盘 IO 抢占)
- Ensembl / CT.gov 05:00 / 05:30 — 错峰到早班前

---

## 7. 辅助表(etl_run_log / etl_quarantine)

### 7.1 etl_run_log(每次 ETL 跑一行)

```sql
CREATE TABLE etl_run_log (
    id              BIGSERIAL PRIMARY KEY,
    source          VARCHAR(32) NOT NULL,           -- 'ncbi_gene' / 'uniprot' / 'ensembl' / 'clinicaltrials'
    run_type        VARCHAR(16) NOT NULL,           -- 'full' / 'incremental'
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    status          VARCHAR(16) NOT NULL DEFAULT 'running',  -- 'running' / 'success' / 'failed' / 'partial'
    records_loaded  BIGINT,
    records_failed  BIGINT,
    md5_verified    BOOLEAN,
    duration_sec    INTEGER,
    error_message   TEXT
);

CREATE INDEX etl_run_log_source_idx ON etl_run_log(source, started_at DESC);
```

**用途**:dashboard 查"最近一次 NCBI Gene 增量跑了多久 / 加载多少条 / 失败多少条"。

### 7.2 etl_quarantine(隔离失败记录,不阻塞主流程)

```sql
CREATE TABLE etl_quarantine (
    id              BIGSERIAL PRIMARY KEY,
    run_id          BIGINT REFERENCES etl_run_log(id),
    source          VARCHAR(32) NOT NULL,
    raw_record      JSONB,                          -- 原始记录原文
    error_reason    TEXT,                            -- Pydantic validation 失败原因
    quarantined_at  TIMESTAMP NOT NULL DEFAULT now(),
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_at     TIMESTAMP
);
```

**处置流程**:
- ETL 跑通时 `etl_quarantine.resolved = FALSE` 比例 < 1% — 正常
- 1-5% — 黄色告警,下次跑前 review
- > 5% — 红色告警,暂停增量,等主人决策

---

## 8. 失败重试与回滚

### 8.1 段级重试(已在 §10.2 提及,本节扩展)

| 段 | 失败类型 | 重试策略 |
|---|---|---|
| 1 下载 | HTTP 5xx / 超时 / md5 不匹配 | 3 次重试,退避 2s/5s/15s;md5 仍不匹配触发"全量重下" |
| 2 解析 | 文件损坏 / 编码异常 | 不重试,直接标记 run 失败,等人工 |
| 3 转换 | Pydantic validation 失败 | 记录入 `etl_quarantine`,**不阻塞主流程** |
| 4 加载 | Neo4j 死锁 / 临时不可用 | 3 次重试,退避 2s/5s/15s;仍失败触发回滚 |

### 8.2 全量入库前的 Neo4j snapshot

```bash
# Phase 1 实施期写在 deployment 脚本中
neo4j-admin database dump neo4j --to-path=/data/snapshots/neo4j-$(date +%Y%m%d).dump
```

仅在"全量入库"前执行(每周一次 NCBI 全量 + 8 周一次 UniProt 全量 + 4 月一次 Ensembl 全量),增量不 snapshot(增量失败可重新跑增量修复)。

**snapshot 保留策略**:最近 3 个全量 snapshot(~3 × 5 GB = 15 GB),超出自动清理最旧。

### 8.3 回滚操作

```bash
# 1. 停 ETL cron
systemctl stop biologyadvisor-etl.service

# 2. 卸 Neo4j
neo4j-admin database load neo4j --from-path=/data/snapshots/neo4j-20260908.dump

# 3. 改 etl_state,把 last_full_sync / last_incr_sync 回退到 snapshot 时刻
psql -c "UPDATE etl_state SET last_full_sync = '2026-09-08 03:00:00' WHERE source = 'ncbi_gene';"

# 4. 重启 ETL
systemctl start biologyadvisor-etl.service
```

回滚预计 30 分钟内完成,Phase 1 启动后第一次实战演练。

---

## 9. 监控信号(读 etl_run_log / etl_state)

| 信号 | 阈值 | 触发动作 |
|---|---|---|
| `etl_run_log.status = 'failed'` | 任一次 | 飞书机器人告警 + 主人邮件 |
| `etl_quarantine.resolved = FALSE` 累计 > 5% | 一次跑 | 飞书机器人黄色告警 |
| `etl_state.status = 'failed'` 持续 > 24h | 24h | 飞书机器人红色告警 + 暂停下次 cron |
| `etl_state.next_run_due < now() AND status='idle'` | 任一源 | 飞书机器人黄色告警("cron 没跑") |
| 某源 `record_count` 较上次减少 > 5% | 一次增量 | 触发"重新全量"安全网 + 告警 |
| UniProt `pending` 对齐累计 > 10% | 一次增量 | 触发"提前全量" + 告警 |
| Neo4j 节点数 < 50 万 | Phase 1 启动 2 周后 | 飞书机器人红色告警("入库不达标") |

Phase 1 实施期在 `app/main.py` 增加 `/api/v1/etl/health` 端点,返回上述信号的 JSON 快照,Web dashboard 拉这个端点渲染。

---

## 10. Phase 1 实施 9 项验收 checklist

Phase 1 启动期(预计 9-13 ~ 9-25)逐项打勾,每项闭合 1 个 commit:

- [ ] `etl_state` / `etl_run_log` / `etl_quarantine` 三表在 PostgreSQL 落地,索引齐全
- [ ] NCBI Gene 首次全量入库完成,`record_count` ≥ 43,000(`tax_id=9606` 子集)
- [ ] NCBI Gene 首次增量入库完成,`last_incr_sync` 写入,`etl_run_log` 至少 2 条(全量 + 增量)
- [ ] UniProt 首次全量入库完成,`record_count` ≥ 20,000(人类 Swiss-Prot),`gene_id` 对齐率 ≥ 95%
- [ ] UniProt 第一次 diff 增量入库完成,`pending` 对齐 < 5%
- [ ] Ensembl 首次 GTF 入库完成,Gene 节点校核与 NCBI Gene 不一致 < 1%
- [ ] Neo4j 6 节点索引 + 8 关系索引落地(`docs/architecture/neo4j-schema-v1.md` §4 全文)
- [ ] 9 项监控信号接入飞书机器人,任一触发有真实告警消息
- [ ] 全量入库前 Neo4j snapshot 自动化脚本跑通,回滚演练 1 次成功

---

## 11. 不做什么

明确**不在本节点范围**:
- ❌ 写 ETL 代码(预计 9-13 ~ 9-25,Phase 1 实施期再做)
- ❌ 申请 NCBI API Key(§5 #4 留主人动作,本文档假设 Key 已就位,凭证读取逻辑 `os.environ['NCBI_API_KEY']`)
- ❌ ClinicalTrials 实体入库(Phase 2,§4.4 仅做可达性)
- ❌ Disease / Drug / Literature 实体入库(Phase 2)
- ❌ 跨库冲突解决策略(如某蛋白 GeneID 在 NCBI 与 UniProt 不一致时以谁为准)— Phase 1 启动首跑后再定
- ❌ PubMed 摘要入 Milvus(RAG 流水线单独成体系,见 Phase 1 §6 第 4 项)

---

## 12. 关联文档

- [[datasource-dump-eval.md]] · §10.5 增量同步钩子(本节点扩展)
- [[datasource-dump-eval.md]] · §6.3 增量方案预览(本节点细化)
- [[datasource-dump-eval.md]] · §10.1 字段映射矩阵(ETL 段 3 转换依据)
- [[datasource-dump-eval.md]] · §10.2 ETL 4 段流水线(本节点沿用)
- [[datasource-dump-eval.md]] · §10.3 Neo4j 入库 Cypher 模板(本节点沿用)
- [[datasource-dump-eval.md]] · §10.4 idmapping 三步走(本节点 §5 增量一致性扩展)
- [[neo4j-schema-v1.md]] · 6 实体 8 关系定义 + 索引约束
- [[api-keys-checklist.md]] · 凭证基线 + QPS 限速
- [[../../项目开发计划.md]] · §6 Phase 1 第 1 项(本文档为其前置)
- [[code-skeleton-bootstrap.md]] · Phase 1 接入点
- `config/clinicaltrials.yaml` · ClinicalTrials 配置骨架

---

## 13. 变更记录

| 日期 | 版本 | 变更 | 触发 |
|---|---|---|---|
| 2026-09-10 | v1.0 | 初稿,完成 §1-§13 全部设计 | 9-10 cron T5 任务(`.plan/20260910.md` 缺失,顾问自选 Phase 1 §6 第 1 项前置) |

---

## 14. 元数据

- 节点耗时:1 次 cron T5 窗口(桌面研究,无实际 ETL 跑)
- 引用源:UniProt 2026_03 release notes / Ensembl release schedule / NCBI Gene FAQ
- 关联任务:`.plan/` 9-10 缺失(连续第 6 天 9-05 ~ 9-10),见 9-09 巡检 §1 预警
- 阶段信号:Phase 0 收尾**延长期第 5 天**(9-06 → 9-10,9-09 巡检 §1 报"延长期第 3 天",本节点再推 2 天)
- 下次更新:Phase 1 实施期(预计 9-13 ~ 9-25)逐项打勾 §10 checklist
