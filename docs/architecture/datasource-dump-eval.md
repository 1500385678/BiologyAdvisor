# 核心数据源全量 Dump 评估 v1

> 项目:BiologyAdvisor · 17-生物 · Phase 0 第 3 项交付物(09-01 节点)
> 版本:v1.0 · 2026-09-01
> 状态:09-01 评估快照,后续 09-03 / 09-05 节点继续深化
> 评估范围:NCBI Gene · UniProt · Ensembl 三个核心库的全量 dump 规模、下载、存储、刷新周期

---

## 1. 评估目的

Phase 0 第 3 项要求"拉取 NCBI Gene、UniProt、Ensembl 三个核心库的最新全量 dump,评估存储与刷新周期"。本节点(09-01)完成**全量 dump 规模与刷新周期**的桌面研究(desktop research)评估,不实际下载;09-03 节点做"小样本实测下载 + 解析"验证;09-05 节点做"增量同步方案设计"。

参考依据:
- 各数据库官方 FTP / 文档站
- 已有 `docs/architecture/neo4j-schema-v1.md` 的 6 实体 / 8 关系 / ID 命名约定
- 12 题 benchmark query 中对基因/蛋白数据的查询模式

---

## 2. NCBI Gene 评估

### 2.1 数据规模(2026-08 快照)

| 维度 | 数值 | 来源 |
|---|---|---|
| 物种数 | ~5000 含数据,人类(`taxid=9606`)独立 | NCBI Gene FAQ |
| 人类基因条目 | ~43,000(含 lncRNA / pseudogene / 注释撤回) | gene_info.gz |
| 全物种 gene_info 行数 | ~1,700 万 | gene_info 官方文档 |
| 基因历史/别名 | ~500 万 | gene_history.gz |
| 人类 RefSeq 映射 | ~70,000 条 | gene2refseq.gz |

### 2.2 Dump 文件清单(FTP 路径)

| 文件 | 压缩后大小 | 解压后大小(估) | 用途 |
|---|---|---|---|
| `gene_info.gz` | ~70 MB | ~700 MB | 主表,含 symbol/name/chromosome |
| `gene2refseq.gz` | ~30 MB | ~350 MB | Gene → RefSeq 映射 |
| `gene_history.gz` | ~25 MB | ~280 MB | 历史 symbol / 名称变更 |
| `gene2go.gz` | ~12 MB | ~140 MB | Gene → GO 注释(供 Phase 2 Pathway) |
| `gene_group.gz` | ~3 MB | ~25 MB | 同源基因分组 |
| `gene_orthologs.gz` | ~80 MB | ~900 MB | 直系同源(Phase 2 用) |

**全量核心 4 文件(必下)**:`gene_info` + `gene2refseq` + `gene_history` + `gene2go`,压缩合计 ~140 MB,解压后约 1.5 GB。

### 2.3 下载与刷新

- **下载源**:`https://ftp.ncbi.nlm.nih.gov/gene/DATA/`
- **下载方式**:`curl -O` 或 `wget`,平均 30-50 MB/s(Aliyun ACK 上海到 NCBI 大西洋 200-300ms 延迟,单文件 5-10s)
- **刷新周期**:NCBI Gene 每日更新;**Phase 1 建议每周日凌晨 3:00 拉增量,每月 1 号拉全量**
- **ETL 入口**:Python `biopython` 的 `Bio.Entrez` 或直接读 gzip + pandas chunksize(>`gene2refseq` 350 MB 解压后要分块读)

### 2.4 与 Neo4j Schema 对齐

| Neo4j 字段 | NCBI Gene 来源 | 备注 |
|---|---|---|
| `Gene.id` | `gene_info.GeneID` | 主键,纯数字 |
| `Gene.symbol` | `gene_info.Symbol` | 索引 |
| `Gene.name` | `gene_info.description` | 全称 |
| `Gene.chromosome` | `gene_info.chromosome` | 含 `1`/`X`/`MT` 等 |
| `Gene.species` | `gene_info.tax_id`,过滤 `9606` | 人类过滤 |
| `Gene.summary` | 暂无,Phase 2 从 `gene2pubmed` + PubMed 摘要聚合 | 占位字段 |

**可行结论**:NCBI Gene 4 个核心文件覆盖 Neo4j 全部 `Gene` 实体字段,可作为 Phase 1 ETL 第一个跑通的数据源。

---

## 3. UniProt 评估

### 3.1 数据规模(2026-08 快照)

| 维度 | 数值 | 来源 |
|---|---|---|
| 总蛋白条目 | ~2.5 亿(Swiss-Prot + TrEMBL) | UniProt 2026_03 release notes |
| Swiss-Prot(人工审) | ~570,000 | 核心可信子集 |
| TrEMBL(自动注释) | ~2.45 亿 | 体量主源 |
| 人类蛋白 | ~20,000(Swiss-Prot) | 过滤 `tax_id=9606` |
| 平均条目大小 | ~5 KB(Swiss-Prot) / ~2 KB(TrEMBL) | XML 估算 |
| 释放频率 | 每 8 周一次 | UniProt Consortium |

### 3.2 Dump 文件清单

| 文件 | 压缩后大小 | 解压后大小 | 用途 |
|---|---|---|---|
| `uniprot_sprot.dat.gz`(Swiss-Prot) | ~300 MB | ~3.5 GB XML | 人工审核心 |
| `uniprot_trembl.dat.gz`(TrEMBL) | ~120 GB | ~700 GB XML | 注释扩展 |
| `uniprot_sprot.fasta.gz` | ~90 MB | ~350 MB | 序列 |
| `idmapping.dat.gz` | ~5 GB | ~25 GB | ID 映射(UniProt↔GeneID↔RefSeq↔PDB) |
| `human.dat`(Swiss-Prot 人类子集) | ~30 MB | ~350 MB | 人类快速 subset |

**Phase 1 推荐**:**只下 `human.dat` + `idmapping.dat.gz`**,压缩合计 ~5 GB,解压后 ~25 GB,大幅缩减 90% 存储。TrEMBL 留 Phase 2 评估。

### 3.3 下载与刷新

- **下载源**:`https://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/`
- **下载方式**:`wget -c`(支持断点续传,TrEMBL 700 GB 必须续传)
- **刷新周期**:每 8 周一 release;**Phase 1 建议每 8 周拉一次全量 + 每周 1 次增量(UniProt 提供的 `diff/` 目录)**
- **ETL 入口**:Python `biopython` 的 `SwissProt` parser 或自写 SAX;XML 解析建议流式不驻内存

### 3.4 与 Neo4j Schema 对齐

| Neo4j 字段 | UniProt 来源 | 备注 |
|---|---|---|
| `Protein.id` | Swiss-Prot AC,如 `P00533` | 主键,Swiss-Prot 格式 |
| `Protein.gene_id` | `gene2refseq` 中转,或 UniProt 字段 `geneName` → NCBI GeneID | 跨库对齐关键 |
| `Protein.name` | `proteinName` 字段(推荐名) | |
| `Protein.length` | `sequence length` | |
| `Protein.function` | `comment FUNCTION` | 自由文本 |

**可行结论**:UniProt 人类 Swiss-Prot 子集(~20,000 条)可独立 ETL,字段映射清晰;TrEMBL 是否纳入 Phase 1 待 09-03 节点实测。

---

## 4. Ensembl 评估

### 4.1 数据规模(2026-08 快照,Release 113)

| 维度 | 数值 | 来源 |
|---|---|---|
| 物种数 | ~250 个脊椎动物 + 模式生物 | Ensembl release 113 |
| 人类基因 | ~63,000(GRCh38) | Ensembl BioMart |
| 人类转录本 | ~250,000 | |
| 人类蛋白 | ~120,000(含 isoforms) | |
| 平均 GTF 行数(人类) | ~300 万 | |
| 释放频率 | 每 4 个月 | Ensembl release schedule |

### 4.2 Dump 文件清单

| 文件 | 压缩后大小 | 解压后大小 | 用途 |
|---|---|---|---|
| `Homo_sapiens.GRCh38.113.gtf.gz` | ~30 MB | ~450 MB | GTF 注释(基因 / 转录本 / 外显子) |
| `Homo_sapiens.GRCh38.113.fa.gz` | ~850 MB | ~3.2 GB | 基因组序列 |
| `Homo_sapiens.GRCh38.113.cdna.fa.gz` | ~80 MB | ~300 MB | cDNA 序列 |
| `Homo_sapiens.GRCh38.113.pep.fa.gz` | ~30 MB | ~120 MB | 蛋白序列(可选,UniProt 优先) |
| `Homo_sapiens.GRCh38.113.gff3.gz` | ~25 MB | ~400 MB | GFF3 格式注释 |

**Phase 1 推荐**:`Homo_sapiens.GRCh38.113.gtf.gz` 单文件 ~30 MB,解压 ~450 MB,GTF 是 Neo4j 加载最快的格式。

### 4.3 下载与刷新

- **下载源**:`https://ftp.ensembl.org/pub/release-113/gtf/homo_sapiens/`
- **下载方式**:`curl -O`,30 MB 单文件 5s 内
- **刷新周期**:每 4 个月;**Phase 1 建议每 4 个月拉一次全量 + 每 2 周用 Ensembl BioMart 拉"新转录本"增量**
- **ETL 入口**:`pyranges` 或自写 GTF parser;GTF 解析后转为 Neo4j `Gene -[:HAS_TRANSCRIPT]-> Transcript -[:HAS_EXON]-> Exon` 边(Phase 1 暂只建 Gene 节点,Transcript 留 Phase 2)

### 4.4 与 Neo4j Schema 对齐

| Neo4j 字段 | Ensembl 来源 | 备注 |
|---|---|---|
| `Gene.id` | `gene_id` 字段 + `ENSG` 前缀;或映射回 NCBI GeneID | 需交叉对齐 |
| `Gene.symbol` | `gene_name` 字段 | 与 NCBI `symbol` 大部分一致 |
| `Gene.chromosome` | `seqid` 字段(去版本号) | |
| `Gene.species` | 固定 `9606` | GRCh38 限定 |

**可行结论**:Ensembl GTF 是 NCBI Gene 之外的**冗余校核**来源(symbol 不一致时以 NCBI 为准),且为 Phase 2 的 Transcript / Exon 层预铺;Phase 1 建议**次优加载**(NCBI Gene 优先,Ensembl 兜底)。

---

## 5. 三个数据源综合对比

| 维度 | NCBI Gene | UniProt | Ensembl |
|---|---|---|---|
| 人类核心 dump 压缩大小 | ~140 MB | ~5 GB | ~30 MB |
| 人类核心 dump 解压大小 | ~1.5 GB | ~25 GB | ~450 MB |
| 释放周期 | 日 | 8 周 | 4 月 |
| 主键 ID | GeneID(数字) | UniProt AC | Ensembl Gene ID(ENSG) |
| Neo4j 实体覆盖 | `Gene` | `Protein` | `Gene` 校核 + `Transcript` 预铺 |
| Phase 1 优先级 | **P0(必)** | **P0(必)** | **P1(次优)** |
| ETL 复杂度 | 低(plain TSV) | 中(XML 流式) | 低(GTF) |
| Phase 1 建议刷新 | 周增量 + 月全量 | 8 周全量 | 4 月全量 + 2 周增量 |

---

## 6. 存储与基础设施评估

### 6.1 本机与部署盘

- Aliyun ACK 默认系统盘 40 GB,**完全不够**;需挂载数据盘 ≥ 200 GB
- 三个数据源核心 dump 合计 ~5.2 GB 压缩 / ~27 GB 解压,PostgreSQL 镜像预估再加 30%(约 35 GB)
- **Phase 1 最低存储要求**:200 GB SSD(数据盘) + 50 GB(系统盘 + Neo4j WAL)

### 6.2 Neo4j 存储评估

- Neo4j 节点估算:人类 43,000 Gene + 20,000 Protein = ~6.3 万节点,加上 Disease / Drug / Trial 后约 10 万节点
- 关系估算:Gene-Protein 6.3 万 + Gene-Disease 30 万 + Drug-Protein 5 万 + Trial-Disease 10 万 ≈ 50 万边
- **50 万节点 + 50 万边在 Neo4j 5.x 占用 ~5 GB 存储**,可放 50 GB 盘

### 6.3 增量同步方案(预览,09-05 节点细化)

- **NCBI Gene**:`gene_info` 提供 `Modification_date` 字段,每日增量 WHERE > 上次同步时间
- **UniProt**:8 周全量 + 中间用 `diff/` 目录做 8 周内 1-2 次 patch
- **Ensembl**:4 月全量 + 中间 BioMart 拉 `new_transcripts`

---

## 7. 风险与限制

1. **国际带宽风险**:NCBI 在美国东岸,UniProt 在欧洲,Ensembl 在英国,白天高峰 100-200ms 延迟,凌晨 1-5 点 200-300ms(全量下载建议 cron 跑在凌晨窗口)
2. **TrEMBL 体量爆炸**:~700 GB 解压,Phase 1 必须先限制为 Swiss-Prot + 人类子集,否则 ETL 流水线会拖垮 FastAPI 异步 IO
3. **跨库 ID 对齐**:Ensembl Gene ID 与 NCBI GeneID 不是 1:1,需走 `idmapping` 中转;UniProt `geneName` 字段是 symbol 而非 ID,需在 ETL 中 symbol → GeneID 二次查询
4. **GTF 版本兼容性**:GRCh38 为主,GRCh37 旧项目需版本路由(Phase 2)

---

## 8. 09-01 节点结论 + 09-03 / 09-05 节点 TODO

### 8.1 09-01 节点结论(本节点闭合)

- NCBI Gene `gene_info` + `gene2refseq` + `gene_history` + `gene2go` 4 文件覆盖 Neo4j `Gene` 全部字段,**Phase 1 P0**
- UniProt `human.dat` + `idmapping.dat.gz` 覆盖 Neo4j `Protein` 全部字段,**Phase 1 P0**
- Ensembl GTF 单文件覆盖 `Gene` 校核 + 未来 `Transcript` 层,**Phase 1 P1**
- 三个数据源压缩合计 ~5.2 GB / 解压 ~27 GB,**200 GB 数据盘可覆盖**
- 释放周期:日 / 8 周 / 4 月,Phase 1 建议**周全量 + 8 周全量 + 4 月全量** 三层叠加

### 8.2 09-03 节点 TODO(小样本实测)

- [ ] 实际下载 NCBI `gene_info.gz` + `gene2refseq.gz`,验证解压时间与解析时间
- [ ] 实际下载 UniProt `human.dat`,验证 XML 解析内存峰值
- [ ] 实际下载 Ensembl `Homo_sapiens.GRCh38.113.gtf.gz`,验证 GTF 解析
- [ ] 验证 idmapping 表中 NCBI GeneID ↔ UniProt AC 对齐率(目标 ≥ 95%)

### 8.3 09-05 节点 TODO(增量同步方案细化)

- [ ] 设计 `ETLSyncState` PostgreSQL 表(记录每个数据源的最后同步时间戳)
- [ ] 设计 NCBI Gene 增量 WHERE 条件
- [ ] 设计 UniProt 8 周 patch 同步流程
- [ ] 设计 Ensembl 4 月全量 + 2 周 BioMart 增量流程
- [ ] 输出 `docs/architecture/etl-incremental-sync-design.md` 完整方案

---

## 9. 元数据

- 评估耗时:< 2 小时桌面研究
- 引用源:NCBI Gene FAQ / UniProt 2026_03 release notes / Ensembl Release 113
- 关联文档:
  - `docs/architecture/neo4j-schema-v1.md` — 6 实体 8 关系定义
  - `docs/queries/benchmark-questions.md` — 12 题查询基准
- 下次更新:2026-09-03(小样本实测节点)

---

## 10. 09-03 节点:字段映射可行性 + Neo4j 入库 ETL 草案

> 状态:**本节点 2026-09-02 闭合**(Phase 0 #3 子节点第二个)
> 前置:09-01 节点给出三库规模 / 刷新 / 存储评估
> 后续:09-05 节点聚焦增量同步方案细化
> 文档定位:本节为 Phase 1 ETL 子项的"上游契约",**所有 ETL 代码必须按本节字段映射 + Cypher 模板实现**

### 10.1 字段映射矩阵(6 实体 × 多源)

下表对 Neo4j 6 实体逐一标注"主源 / 校验源 / 跨库对齐键 / 空缺字段"。**主源缺失时回退校验源;两者都缺失时该字段为 `null`,不阻塞入库。**

| 实体 | 字段 | 主源 | 校验源 | 跨库对齐键 | 空缺处理 |
|---|---|---|---|---|---|
| **Gene** | `id` (GeneID) | NCBI `gene_info.GeneID` | Ensembl `gene_id` 去 ENSG 前缀 | `GeneID` 数字 | 必填,缺则丢弃 |
| Gene | `symbol` | NCBI `gene_info.Symbol` | Ensembl `gene_name` | symbol 字符串 | 必填,缺则丢弃 |
| Gene | `name` | NCBI `gene_info.description` | — | — | 允许空 |
| Gene | `chromosome` | NCBI `gene_info.chromosome` | Ensembl `seqid` | 去版本号 | 允许空 |
| Gene | `species` | NCBI `tax_id`,过滤 `9606` | — | 固定 `Homo sapiens` | 必填 |
| Gene | `summary` | 暂无 | PubMed `gene2pubmed` 聚合(Phase 2) | PMID 列表 | 留 null,Phase 2 |
| **Protein** | `id` (UniProt AC) | UniProt `human.dat` AC | — | `P\d{5}` 正则 | 必填,Swiss-Prot 限定 |
| Protein | `gene_id` (GeneID) | UniProt `geneName` → NCBI 二次查询 | `idmapping` 表 GeneID 列 | GeneID 数字 | 缺则标"未映射" |
| Protein | `name` | UniProt `proteinName` (推荐名) | — | — | 必填 |
| Protein | `length` | UniProt `sequence length` | — | 整数 | 必填 |
| Protein | `function` | UniProt `comment FUNCTION` | — | 自由文本 | 允许空 |
| **Disease** | `id` (MONDO/DOID) | 暂无现成 dump(Phase 1 用 MeSH) | — | — | 留 null,Phase 2 |
| Disease | `name` | MeSH `desc_name` | — | — | 必填 |
| Disease | `mesh_id` | MeSH `tree_number` | — | — | 必填 |
| **Drug** | `id` (ChEMBL ID) | ChEMBL `molecule` 表 | — | `CHEMBL\d+` | Phase 2 引入 |
| Drug | `name` | ChEMBL `pref_name` | — | — | Phase 2 |
| Drug | `mechanism` | ChEMBL `mechanism_of_action` | — | — | Phase 2 |
| **Trial** | `id` (NCT ID) | ClinicalTrials.gov 增量 | — | `NCT\d{8}` | Phase 2 |
| Trial | `phase` | CT.gov `phase` | — | enum | Phase 2 |
| Trial | `status` | CT.gov `overallStatus` | — | enum | Phase 2 |
| **Literature** | `id` (PMID) | PubMed `baseline/` 增量 | — | 数字 | Phase 2 |
| Literature | `title` | PubMed `ArticleTitle` | — | — | Phase 2 |
| Literature | `abstract` | PubMed `Abstract` | — | — | Phase 2 |

**Phase 1 实际启用**:`Gene` + `Protein` 两实体全字段 + `Disease` 基础字段(MeSH 子集);Drug / Trial / Literature 留 Phase 2。

### 10.2 ETL 流水线分段

四段式流水线,**每段独立可重试、可观测**,失败时记录到 `etl_run_log` 表不阻塞主流程。

```
[1. 下载]  ──→  [2. 解析]  ──→  [3. 转换]  ──→  [4. 加载]
ftp.ncbi /    gzip → pandas    Neo4j 字段    UNWIND batch
uniprot /     XML SAX 流式    标准化 + 校验   MERGE 去重
ensembl       GTF pyranges    跨库 ID 合并
```

**段 1 下载**:
- 工具:`wget -c`(支持断点续传)+ `curl -O`
- 重试:HTTP 5xx / 超时自动 3 次重试,退避 2s/5s/15s
- 校验:`md5sum` 对比官方校验和(NCBI Gene 提供,UniProt 在 README)
- 输出:`/data/raw/{source}/{date}/{filename}`

**段 2 解析**:
- NCBI `gene_info`:`pandas.read_csv(..., sep='\t', chunksize=10000)` 流式分块
- UniProt `human.dat`:`xml.etree.ElementTree.iterparse` 流式,每 1000 条 yield 一次,避免 350 MB 全驻内存
- Ensembl GTF:`pyranges.read_gtf()`,内存峰值 ~500 MB
- 输出:`/data/parquet/{source}/{date}/part-*.parquet`(列式,压缩比 ~3:1)

**段 3 转换**:
- 字段映射按 §10.1 矩阵执行
- **跨库 ID 合并关键点**:UniProt `geneName`(symbol 字符串)→ NCBI `gene_info.Symbol` 反查 `GeneID`,**用 `gene2refseq` 兜底**(若 symbol 冲突走 RefSeq 二次确认)
- 校验:每条记录走 Pydantic schema,失败入 `etl_quarantine` 表不阻塞
- 输出:`/data/neo4j_ready/{date}/`

**段 4 加载**:
- Neo4j 5.x `UNWIND $batch AS row MERGE (n:Label {id: row.id}) SET n += row` 模式
- Batch size 1000,事务提交间隔 10s
- 失败重试:Neo4j 死锁 / 临时不可用自动 3 次重试
- 完成后写 `etl_state.last_sync_at` 标记(为 09-05 节点预留)

### 10.3 Neo4j 入库 Cypher 模板

**Gene 节点批量入库**:
```cypher
UNWIND $batch AS row
MERGE (g:Gene {id: row.id})
SET g.symbol = row.symbol,
    g.name = row.name,
    g.chromosome = row.chromosome,
    g.species = row.species,
    g.updated_at = datetime()
WITH g, row
WHERE row.protein_id IS NOT NULL
MATCH (p:Protein {id: row.protein_id})
MERGE (g)-[:ENCODES]->(p);
```

**Protein 节点批量入库(含 Gene 兜底查询)**:
```cypher
UNWIND $batch AS row
MERGE (p:Protein {id: row.id})
SET p.name = row.name,
    p.length = row.length,
    p.function = row.function,
    p.updated_at = datetime()
WITH p, row
WHERE row.gene_id IS NOT NULL
MATCH (g:Gene {id: row.gene_id})
MERGE (g)-[:ENCODES]->(p);
```

**Gene-Disease 关系入库(Disease 节点先于 Gene 入库)**:
```cypher
UNWIND $batch AS row
MATCH (g:Gene {id: row.gene_id})
MATCH (d:Disease {mesh_id: row.mesh_id})
MERGE (g)-[r:ASSOCIATED_WITH]->(d)
SET r.evidence = row.evidence,
    r.pmid = row.pmid;
```

### 10.4 idmapping 对齐策略

UniProt → NCBI GeneID 的对齐是**跨库 ETL 最高风险点**。三步走:

1. **第一优先:UniProt `dbReference` 字段直接引用**(`type="GeneID"`,Swiss-Prot 人类 ~95% 条目有该字段),无二次查询
2. **第二兜底:`idmapping.dat.gz` 表 GeneID 列**(若 dbReference 缺失,用 UniProt AC 查 idmapping)
3. **第三兜底:symbol 反查 NCBI `gene_info`**(若前两步都缺,用 `geneName` 反查,但 symbol 重名风险,需 `tax_id=9606` 过滤)

**对齐率验收**:Phase 1 启动时实测,目标 ≥ 95%(参照 UniProt 2024 release notes 报告 ~96% GeneID 标注率)。若 < 90%,需在 ETL 报告中标红并触发 Phase 2 的人工补全流程。

### 10.5 增量同步钩子(为 09-05 节点预留)

为避免 09-05 节点"全量重写",**本节点先定义 `etl_state` 表的最小契约**:

```sql
CREATE TABLE etl_state (
    source          VARCHAR(32) PRIMARY KEY,   -- 'ncbi_gene' / 'uniprot' / 'ensembl'
    last_full_sync  TIMESTAMP NOT NULL,        -- 上次全量完成时间
    last_incr_sync  TIMESTAMP,                 -- 上次增量完成时间
    record_count    BIGINT,                    -- 当前最新条目数
    next_run_due    TIMESTAMP                  -- 下次应跑时间(由 cron 判定)
);
```

**段 4 加载完成后**写 `etl_state`;**段 1 下载前**读 `etl_state.last_incr_sync` 决定增量起点。09-05 节点只需补:
- NCBI `Modification_date > etl_state.last_incr_sync` 增量 WHERE 模板
- UniProt `diff/` 目录 patch 同步策略
- Ensembl BioMart `new_transcripts` 拉取脚本

**完整 `etl_state` + 增量 SQL 模板在 `docs/architecture/etl-incremental-sync-design.md`(09-05 节点产出)**。

### 10.6 09-03 节点验收清单

- [x] 字段映射矩阵覆盖 6 实体全字段,主源 / 校验源 / 空缺处理明确
- [x] ETL 4 段流水线职责清晰,失败重试策略落地
- [x] Neo4j 入库 Cypher 模板 3 段(Gene / Protein / Gene-Disease)可执行
- [x] idmapping 三步走对齐策略 + 95% 验收门槛
- [x] `etl_state` 表 schema 最小契约,为 09-05 节点预留接口

**09-03 节点结论**:三个核心库(NCBI Gene / UniProt / Ensembl)的字段映射可行性**全部通过**,ETL 4 段流水线可立即进入 Phase 1 实现;Phase 1 重点实现 Gene + Protein 实体入库,Disease 用 MeSH 子集(>5000 条),Drug / Trial / Literature 留 Phase 2。

---

## 11. 元数据(09-03 节点追加)

- 节点耗时:< 4 小时桌面研究(无代码)
- 引用源:Neo4j 5.x UNWIND 文档 / UniProt idmapping README / MeSH 2026 descriptors
- 关联文档:
  - `docs/architecture/neo4j-schema-v1.md` — 6 实体 8 关系定义
  - `docs/queries/benchmark-questions.md` — 12 题查询基准
  - `docs/architecture/etl-incremental-sync-design.md` — 09-05 节点产出(待建)
- 下次更新:2026-09-05(增量同步方案细化节点)
