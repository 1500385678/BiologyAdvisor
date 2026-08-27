# BiologyAdvisor · Benchmark Query 样例(Phase 1 验收基准)

> **目的**:为 Phase 1 MVP 提供 12 道高频 query 样例,作为 LLM + Tool Use 闭环的客观验收基准。
> **对应计划**:项目开发计划.md §5 Phase 0 第 5 项
> **创建日期**:2026-08-28
> **设计原则**:覆盖 3 类目标用户(科研 / 产业 / 投资) × 3 个难度档(基础查询 / 交叉推理 / 前沿评估),每题必带可验证的"期望字段"而非自由文本。

---

## 一、分类矩阵

| 难度 \ 用户 | 科研(高校/研究所) | 产业(CRO/药企) | 投资(Biotech/PE) |
|---|---|---|---|
| **L1 基础查询** | Q1 / Q4 | Q2 | Q3 |
| **L2 交叉推理** | Q5 | Q6 / Q7 | Q8 |
| **L3 前沿评估** | Q9 | Q10 / Q11 | Q12 |

合计 **12 题**。

---

## 二、L1 基础查询(4 题 · 准确率阈值 ≥ 85%)

### Q1 · EGFR 蛋白结构与染色体定位(科研)
- **用户场景**:研究生写论文前快速核对基因基本信息
- **Query**:"EGFR 基因位于哪条染色体?编码蛋白有多少个氨基酸?"
- **期望字段**:`chromosome`=7p11.2 · `protein_length_aa`=1210 · `uniprot_id`=P00533
- **数据源**:NCBI Gene + UniProt
- **工具路径**:`ncbi_gene(symbol="EGFR")` → `uniprot_lookup(id="P00533")`

### Q2 · 阿美替尼靶点与适应症(产业)
- **用户场景**:药企立项前核对竞品基本信息
- **Query**:"阿美替尼(Aumolertinib)的靶点是什么?已获批的适应症?"
- **期望字段**:`target`=EGFR(T790M) · `approved_indications`=["非小细胞肺癌(NSCLC)二线 T790M+"]
- **数据源**:ChEMBL + DrugBank + NMPA 批件库
- **工具路径**:`chembl_drug(name="Aumolertinib")` → `nmpa_approval()`

### Q3 · NSCLC 在研管线数量(投资)
- **用户场景**:投资经理快速估算赛道拥挤度
- **Query**:"目前全球针对非小细胞肺癌(NSCLC)的 III 期临床试验有多少项?"
- **期望字段**:`phase=III` · `condition="Non-Small Cell Lung Carcinoma"` · 返回数字 + 列表前 5
- **数据源**:ClinicalTrials.gov
- **工具路径**:`clinicaltrials_search(condition="NSCLC", phase="III", status=["Recruiting","Active, not recruiting"])`

### Q4 · TP53 在泛癌中的突变频率(科研)
- **用户场景**:研究生做泛癌分析前查基线
- **Query**:"TP53 在 TCGA 泛癌数据集中总体突变频率是多少?突变最常见的 3 个位点?"
- **期望字段**:`overall_mut_freq` ≥ 30% · `top3_hotspots` = [R175H, R248Q, R273H]
- **数据源**:cBioPortal API(若可用)/ COSMIC
- **工具路径**:`cbioportal_query(gene="TP53", study="pan-cancer")`

---

## 三、L2 交叉推理(4 题 · 准确率阈值 ≥ 70%)

### Q5 · EGFR-TKI 耐药机制综述(科研)
- **Query**:"EGFR 突变 NSCLC 患者在接受第三代 TKI 奥希替尼(Osimertinib)治疗后的主要获得性耐药机制有哪些?按发生率排序前 3?"
- **期望字段**:Top 3 = [C797S 突变 / MET 扩增 / HER2 扩增] · 每条需附 PMID
- **数据源**:PubMed(近 3 年综述) + ClinicalTrials
- **工具路径**:`pubmed_search(q="Osimertinib resistance mechanism", years=3)` → LLM 抽取 + 排序

### Q6 · 同一靶点的国内竞品扫描(产业)
- **Query**:"国内已上市或进入 III 期的 KRAS G12C 抑制剂有哪些?列出公司、适应症、最新进展时间"
- **期望字段**:列表 ≥ 3 个(信达 IBI351 / 君实 JS-006 / 益方 D-1553 等) · 每条带 ClinicalTrials NCT ID
- **数据源**:ClinicalTrials.gov + NMPA CDE 公示 + 公司公告
- **工具路径**:`clinicaltrials_search(target="KRAS G12C", region="China", phase>=II)` + 公告 RAG

### Q7 · 适应症拓展:PD-1 抑制剂在结直肠癌的进展(产业)
- **Query**:"PD-1 抑制剂在 MSI-H/dMMR 结直肠癌中的最新 III 期数据?客观缓解率(ORR)与中位无进展生存期(mPFS)?"
- **期望字段**:Keynote-177 数据:ORR ≈ 44% / mPFS ≈ 16.5 月 · 附 PMID 与 NCT ID
- **数据源**:PubMed + ClinicalTrials
- **工具路径**:`pubmed_search` + `clinicaltrials_get(nct="NCT02563002")`

### Q8 · 估值锚定:ADC 赛道上市公司管线(投资)
- **Query**:"全球 ADC(抗体偶联药物)上市公司中,按在研管线数量排名前 5 的公司及主要靶点?"
- **期望字段**:Top 5 = [Seagen / Daiichi Sankyo / Gilead(Kite) / AZ / Roche] · 主要靶点含 HER2 / TROP2 / Nectin-4
- **数据源**:公司管线公告(EDGAR / 港交所披露易 / 上交所)
- **工具路径**:`company_pipeline_lookup(company=top10_adc_firms)` + LLM 排序

---

## 四、L3 前沿评估(4 题 · 准确率阈值 ≥ 60%,评估"敢说不会"的能力)

### Q9 · 新型 RNA 编辑工具的临床前证据(科研)
- **Query**:"ADAR-mediated RNA editing 在体内的脱靶率最近一次系统评估?有哪些代表性递送系统?"
- **期望字段**:LNP / AAV / 外泌体三类递送 + 脱靶率数字(如 < 1%) · 至少 2 篇近 2 年高引文献
- **数据源**:PubMed(高引) + bioRxiv 预印本
- **工具路径**:`pubmed_search` + `biorxiv_search(q="ADAR RNA editing in vivo")`

### Q10 · PROTAC 分子成药性评估(产业)
- **Query**:"目前进入临床的 PROTAC 分子有哪几个?靶点、研发公司、当前阶段、遇到的主要挑战?"
- **期望字段**:≥ 3 个临床 PROTAC(ARV-110 / ARV-471 / NX-2127 等) + 挑战 = 口服生物利用度 / 耐药
- **数据源**:ClinicalTrials + 公司管线 + 综述
- **工具路径**:`clinicaltrials_search(keyword="PROTAC")` + `pubmed_search(q="PROTAC clinical challenges")`

### Q11 · 细胞治疗在自免疾病的早期信号(产业)
- **Query**:"CAR-T 治疗系统性红斑狼疮(SLE)目前已有的临床数据?样本量、缓解率、随访时长?"
- **期望字段**:≥ 2 项研究(如 Erlangen / 上海长征) · 总缓解率 ≥ 60% · 附 PMID + NCT ID
- **数据源**:PubMed + ClinicalTrials
- **工具路径**:`pubmed_search(q="CAR-T SLE lupus")` + `clinicaltrials_search(condition="Lupus")`

### Q12 · AI 制药公司 BD 价值评估(投资)
- **Query**:"过去 18 个月 AI 制药领域披露的 License-out 交易金额 Top 3?标的分子类型、买受人、里程碑总额?"
- **期望字段**:Top 3 含 Recursion/Exscientia/Insilico 等代表性交易 · 金额 + 标的类型
- **数据源**:公司公告 + 行业新闻 + SDx 数据库(如可访问)
- **工具路径**:`news_search` + LLM 抽取 + 金额排序
- **额外要求**:必须返回"信息不足时主动声明 + 给出已知最强 3 个候选",**禁止编造金额**

---

## 五、Phase 1 验收口径

| 维度 | L1 | L2 | L3 |
|---|---|---|---|
| 准确率门槛 | ≥ 85% | ≥ 70% | ≥ 60% |
| 幻觉率(无引用答案) | ≤ 5% | ≤ 10% | ≤ 20% |
| 平均响应时长 | ≤ 8s | ≤ 15s | ≤ 25s |
| 引用回链完整度 | 100% 有 PMID/DOI/ID | ≥ 90% | ≥ 70% |

**Phase 1 通过条件**:L1 全部通过 + L2 至少 3 题通过 + L3 至少 2 题"敢说不会"。

---

## 六、不做什么(避免 scope creep)

- ❌ 不在本题库中加 LLM 主观打分题(如"评价这篇论文的创新性")——超出 Phase 1 工具能力
- ❌ 不加中文/英文互译题——属于 NLP 基础能力,不在生物知识图谱验证范围
- ❌ 不加需要付费数据库(Subscription / SDx)独占答案的题——避免 LLM 因权限幻觉
- ❌ 不加图片解读题——Web App 视觉模块属 Phase 2

---

## 关联文档

- [[../architecture/neo4j-schema-v1.md]] — 节点/关系 schema,所有 query 落点对应 6 类节点
- [[../../项目开发计划.md]] §5 Phase 0 第 5 项勾选
- [[../../Inspiration/00-索引.md]] — 题库素材的"基因/疾病/药物/文献"四类映射

## 变更记录

- 2026-08-28 · v1.0 · 12 题初版,与 Phase 0 计划同步落地
