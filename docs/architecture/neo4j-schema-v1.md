# Neo4j Schema 设计稿 v1

> 项目:BiologyAdvisor · 17-生物 · Phase 0 第 4 项交付物
> 版本:v1.0 · 2026-08-27
> 状态:草案,待 Phase 1 ETL 跑通后回填真实字段约束

---

## 1. 设计原则

- **5 层实体 + 1 层证据**:Gene / Protein / Disease / Drug / Trial 五层业务实体,Literature 作为证据层(边上挂载而非孤立节点)
- **ID 优先**:所有实体主键使用权威数据库 ID(NCBI Gene ID、UniProt AC、MONDO ID、ChEMBL ID、ClinicalTrials NCT ID、PubMed PMID),便于跨库对齐
- **关系方向约定**:从"被研究对象"指向"研究方向"(`Gene -[ASSOCIATED_WITH]-> Disease`、`Drug -[TARGETS]-> Protein`),保证多数查询从 Gene/Disease 出发的子图是单向展开
- **轻元数据**:描述性字段(text/JSON)放 PostgreSQL 镜像,Neo4j 只存结构化关键字段与图遍历所需的边
- **可扩展**:节点用 `(:Entity {type: 'Gene'})` 形式,允许 Phase 2 增加 `Pathway / Variant / SideEffect` 等新层

---

## 2. 节点 Schema(6 类)

### 2.1 Gene(基因)

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `id` | string(主键) | NCBI Gene ID,如 `1956` | NCBI Gene |
| `symbol` | string(索引) | 官方符号,如 `EGFR` | NCBI Gene |
| `name` | string | 全称 | NCBI Gene |
| `chromosome` | string | 染色体定位,如 `7p11.2` | NCBI Gene |
| `species` | string(默认 `9606`) | 分类学 ID,人为 `9606` | NCBI Gene |
| `summary` | string | 简介 | NCBI Gene |

### 2.2 Protein(蛋白)

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `id` | string(主键) | UniProt AC,如 `P00533` | UniProt |
| `gene_id` | string(索引) | 反向指向 Gene.id | UniProt / Ensembl |
| `name` | string | 推荐名 | UniProt |
| `length` | int | 氨基酸数 | UniProt |
| `function` | string | 功能描述 | UniProt |
| `organism` | string(默认 `Homo sapiens`) | 物种 | UniProt |

### 2.3 Disease(疾病)

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `id` | string(主键) | MONDO ID 或 DOID,如 `MONDO:0005233` | Mondo Disease Ontology |
| `name` | string(索引) | 疾病名 | MONDO / DOID |
| `icd11` | string | ICD-11 编码(可选) | WHO |
| `mesh` | string | MeSH 术语(可选) | NLM |
| `category` | string | 大类(肿瘤/代谢/神经/...) | 内部标注 |
| `prevalence` | float | 患病率(每 10 万人,可选) | 文献汇总 |

### 2.4 Drug(药物)

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `id` | string(主键) | ChEMBL ID,如 `CHEMBL267720` | ChEMBL |
| `name` | string(索引) | 通用名 | ChEMBL |
| `synonyms` | string[] | 别名(含中文) | ChEMBL |
| `max_phase` | int(0-4) | 最高研发阶段 | ChEMBL |
| `mechanism` | string | MoA 简述 | ChEMBL |
| `first_approval` | int(可选) | 首批适应症获批年份 | ChEMBL |

### 2.5 Trial(临床试验)

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `id` | string(主键) | NCT ID,如 `NCT02581565` | ClinicalTrials.gov |
| `title` | string | 试验标题 | CT.gov |
| `status` | string | Recruiting / Active / Completed / ... | CT.gov |
| `phase` | string | Phase 1/2/3/4 | CT.gov |
| `condition` | string | 招募病种(MONDO 名) | CT.gov |
| `start_date` | date | 启动日期 | CT.gov |
| `enrollment` | int | 计划入组 | CT.gov |

### 2.6 Literature(文献,作证据层)

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| `id` | string(主键) | PubMed PMID,如 `32344890` | PubMed |
| `title` | string | 题名 | PubMed |
| `year` | int | 出版年 | PubMed |
| `journal` | string | 期刊 | PubMed |
| `abstract` | string | 摘要(可入 Milvus) | PubMed |

---

## 3. 关系 Schema(8 类核心)

| 关系 | From → To | 属性 | 业务含义 |
|---|---|---|---|
| `ENCODES` | Gene → Protein | `confidence: float` | 基因编码蛋白(1:1 主导,部分 1:N 剪接) |
| `ASSOCIATED_WITH` | Gene → Disease | `score: float, source: string` | 基因-疾病关联(GWAS / OMIM / 文献) |
| `TARGETS` | Drug → Protein | `action_type: string, ref: string` | 药物作用靶点(抑制剂/激动剂/调节剂) |
| `INDICATED_FOR` | Drug → Disease | `max_phase: int, status: string` | 适应症 |
| `INVESTIGATES` | Trial → Gene\|Drug\|Disease | `arm: string` | 试验研究对象 |
| `CITES` | Literature → Gene\|Protein\|Disease\|Drug | `section: string` | 文献引用证据(主谓宾段落) |
| `INTERACTS_WITH` | Protein → Protein | `method: string, score: float` | 蛋白互作(STRING / BioGRID) |
| `PARTICIPATES_IN` | Protein → Pathway | `evidence: string` | 通路参与(Reactome,Phase 2 引入) |

> 关系边均挂载 `Literature` 引用,通过 `CITES` 边的多源汇聚保证可溯源。

---

## 4. 索引与约束

```cypher
// 唯一约束
CREATE CONSTRAINT gene_id IF NOT EXISTS FOR (g:Gene) REQUIRE g.id IS UNIQUE;
CREATE CONSTRAINT protein_id IF NOT EXISTS FOR (p:Protein) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT disease_id IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT drug_id IF NOT EXISTS FOR (d:Drug) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT trial_id IF NOT EXISTS FOR (t:Trial) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT lit_id IF NOT EXISTS FOR (l:Literature) REQUIRE l.id IS UNIQUE;

// 业务索引
CREATE INDEX gene_symbol IF NOT EXISTS FOR (g:Gene) ON (g.symbol);
CREATE INDEX protein_name IF NOT EXISTS FOR (p:Protein) ON (p.name);
CREATE INDEX disease_name IF NOT EXISTS FOR (d:Disease) ON (d.name);
CREATE INDEX drug_name IF NOT EXISTS FOR (d:Drug) ON (d.name);
CREATE INDEX trial_status IF NOT EXISTS FOR (t:Trial) ON (t.status);

// 关系索引(高频查询边)
CREATE INDEX assoc_score IF NOT EXISTS FOR ()-[r:ASSOCIATED_WITH]-() ON (r.score);
CREATE INDEX drug_phase IF NOT EXISTS FOR ()-[r:INDICATED_FOR]-() ON (r.max_phase);
```

---

## 5. 最小 Cypher 样例

### 5.1 "EGFR 在非小细胞肺癌中的耐药机制"风格查询

```cypher
// 找到 EGFR → 非小细胞肺癌 → 现有靶向药 → 互作蛋白 → 通路
MATCH (g:Gene {symbol: 'EGFR'})-[:ASSOCIATED_WITH]->(d:Disease)
WHERE d.name CONTAINS 'non-small cell lung'
MATCH (drug:Drug)-[:TARGETS]->(:Protein {gene_id: g.id})
MATCH (drug)-[:INDICATED_FOR]->(d)
MATCH (p:Protein {gene_id: g.id})-[:INTERACTS_WITH]->(partner:Protein)
RETURN drug.name, drug.max_phase, partner.name, d.name
LIMIT 25;
```

### 5.2 "靶点 X 还有什么通路没做过药"查询

```cypher
MATCH (g:Gene {symbol: $target})-[:ENCODES]->(p:Protein)
MATCH (p)-[r:PARTICIPATES_IN]->(pw:Pathway)
WHERE NOT EXISTS {
  MATCH (anyDrug:Drug)-[:TARGETS]->(p2:Protein)-[:PARTICIPATES_IN]->(pw)
  WHERE anyDrug.max_phase >= 1
}
RETURN DISTINCT pw.name LIMIT 20;
```

---

## 6. 待确认事项(Phase 1 启动前锁定)

- [ ] Pathway 节点是否 Phase 1 就引入(建议推迟到 Phase 2,先 5 层)
- [ ] Variant(SNP/突变)节点是否单独成层(建议作 Gene 下的属性,Phase 2 再升级)
- [ ] SideEffect 节点是否并入 Drug(建议 v2 引入,关联 FAERS / SIDER)
- [ ] 中文名称字段是否双写(Neo4j 加 `name_zh` 或 PostgreSQL 镜像层处理,推荐后者)
- [ ] 边权 `score` 归一化方案(0-1 还是 0-100,需对齐 GWAS Catalog 与 STRING)

---

## 7. 关联文档

- [[../../项目开发计划.md]] · §5 Phase 0 第 4 项任务来源
- [[../../生物顾问开发架构与计划.md]] · §4 技术架构中 Neo4j 5.x 选型
- [[00-索引]](Inspiration/) · 知识图谱相关文献与竞品
