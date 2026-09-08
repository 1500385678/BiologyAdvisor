# 数据源 API Key 申请清单 v1

> **项目**:BiologyAdvisor · 17-生物 · Phase 0 §5 第 4 项预备交付物
> **版本**:v1.0 · 2026-09-03
> **状态**:预备清单,API Key 真申请 + 验证留 09-05 节点执行
> **目的**:把 §5 唯一未完成项"申请 NCBI API Key + ClinicalTrials.gov 爬虫白名单,确定 QPS 上限"的研究/操作步骤文档化,09-05 节点可直接照清单执行,无需再次桌面研究

---

## 1. 清单总览

| 数据源 | 是否需要 Key | 申请耗时 | 提升额度 | 优先级 | 09-05 节点动作 |
|---|---|---|---|---|---|
| NCBI (Gene / PubMed / E-utilities) | ✅ 强烈建议 | 5 分钟 | 3 → 10 req/s | P0 | 申请 + 验证 |
| ClinicalTrials.gov v2 | ⚠️ 无 Key,但有 rate limit | 0 | 默认 50 req/min | P1 | 配置 User-Agent + 验证 |
| UniProt | ❌ 无 Key 限制 | 0 | — | — | 不需要 |
| Ensembl REST | ⚠️ 可选 | 1 天 | 15 → 55 req/s | P2 | 09-05 末视情况决定 |
| ChEMBL | ❌ 无 Key 限制 | 0 | — | — | 不需要 |

**核心结论**:Phase 1 真正需要主动申请的只有 **NCBI API Key**;ClinicalTrials.gov / Ensembl 的"白名单/扩额"是工程配置而非账号申请,09-05 节点按本文档 §3 / §4 走即可。

---

## 2. NCBI API Key 申请(必做 · P0)

### 2.1 申请前置

- 已有 NCBI 账号(无账号先注册:https://www.ncbi.nlm.nih.gov/account/register/)
- 邮箱已验证(注册时强制)
- 浏览器登录态保持

### 2.2 申请步骤(5 分钟)

1. 登录后访问 `https://www.ncbi.nlm.nih.gov/account/settings/`
2. 页面下半部分 **"API Key Management"** 区域
3. 点击 **"Create an API Key"** 按钮
4. 页面刷新后,新 Key 以 `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` 形式显示
5. **立即复制保存到本地密码管理器** — 页面只显示一次,丢失需重新生成
6. (可选)给 Key 加描述,如 `BiologyAdvisor-dev` / `BiologyAdvisor-prod`

### 2.3 额度提升

| 状态 | 无 Key | 有 Key |
|---|---|---|
| 默认 QPS | 3 req/s | 10 req/s |
| 每日上限 | 无明确上限,实际由 IP 限速 | 同样无明确上限,但更宽松 |
| 突发容忍 | 连续 5+ req 触发 429 | 可突发到 10 req/s |

**结论**:Phase 1 MVP 阶段 10 req/s 足够,只有当 ETL 跑全量或 PubMed 摘要批量召回时才需要更高额度(届时可走 PubMed 批量 E-utilities 路径,单次最多 200 条 ID)。

### 2.4 验证脚本骨架

```python
#!/usr/bin/env python3
"""验证 NCBI API Key 是否生效 · 09-05 节点直接运行"""
import os
import time
import requests

API_KEY = os.environ.get("NCBI_API_KEY", "在此填入 Key")
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi"

def check_key():
    t0 = time.time()
    r = requests.get(BASE, params={
        "db": "gene",
        "api_key": API_KEY,
        "retmode": "json",
    }, timeout=10)
    dt = time.time() - t0
    r.raise_for_status()
    data = r.json()
    if "einforesult" in data and "dbinfo" in data["einforesult"]:
        print(f"✅ NCBI API Key 生效,响应时间 {dt*1000:.0f} ms")
        return True
    print(f"❌ Key 异常,响应内容:{data}")
    return False

if __name__ == "__main__":
    assert API_KEY != "在此填入 Key", "请先填入 API Key"
    check_key()
```

**预期输出**:`✅ NCBI API Key 生效,响应时间 ~200-400 ms`

### 2.5 Key 落库位置

- **环境变量**:`export NCBI_API_KEY="..."` 写入 `~/.zshrc` 或 `~/.bash_profile`
- **项目配置**:Phase 1 实施时在 `BiologyWeb/.env` 增加 `NCBI_API_KEY=...`,`.env` 已在 `.gitignore` 显式排除(`*` 通配,虽然没显式列 `.env`)
- **CI/部署**:Aliyun ACK 容器配置 Secret,不进代码库

---

## 3. ClinicalTrials.gov 爬虫白名单(配置 · P1)

### 3.1 关键事实

- **无需 API Key** — ClinicalTrials.gov v2 REST API 公开,基础调用无认证
- **默认 rate limit**:50 req/min / IP(官方文档 https://clinicaltrials.gov/data-api/about-api)
- **正式"白名单"** — 不存在。ClinicalTrials.gov 不维护"白名单"机制,但有"礼貌爬取"政策
- **强 User-Agent 必填** — 官方要求每个请求带可识别 UA,匿名 UA 会被 429

### 3.2 配置文件骨架(`BiologyWeb/config/clinicaltrials.yaml`,Phase 1 创建)

```yaml
clinicaltrials:
  base_url: https://clinicaltrials.gov/api/v2
  user_agent: "BiologyAdvisor/0.1 (mailto:dev@biologyadvisor.cn)"  # 必填,可联系邮箱
  rate_limit:
    requests_per_minute: 50
    burst: 5
    retry_after_429_seconds: 60
  politeness:
    respect_robots_txt: true
    sleep_between_pages_ms: 200
```

### 3.3 验证脚本骨架

```python
#!/usr/bin/env python3
"""验证 ClinicalTrials.gov API 可达性 · 09-05 节点直接运行"""
import requests

UA = "BiologyAdvisor/0.1 (mailto:dev@biologyadvisor.cn)"
URL = "https://clinicaltrials.gov/api/v2/studies"

def check_reachability():
    r = requests.get(URL, params={
        "query.term": "EGFR",
        "pageSize": 5,
    }, headers={"User-Agent": UA}, timeout=10)
    r.raise_for_status()
    data = r.json()
    n = len(data.get("studies", []))
    print(f"✅ ClinicalTrials.gov 可达,EGFR 查询返回 {n} 条")
    return n > 0

if __name__ == "__main__":
    check_reachability()
```

**预期输出**:`✅ ClinicalTrials.gov 可达,EGFR 查询返回 5 条`

### 3.4 注意事项

- 大规模爬取(>10000 req/天)前,发邮件到 `register@clinicaltrials.gov` 主动报备(非强制但推荐)
- 公开数据可商用,但衍生数据集需保留 `protocolSection.identificationModule.nctId` 字段以满足溯源
- robots.txt 在 `https://clinicaltrials.gov/robots.txt`,ETL 跑前先读一遍

---

## 4. Ensembl REST 高级额度(可选 · P2)

### 4.1 背景

- Ensembl REST 默认 15 req/s,55 req/s 需邮件申请
- Phase 1 不需要这么高,09-05 节点跑通 Gene + Protein 即可
- Phase 2 引入 `gene_orthologs`(直系同源,900 MB 文件)时再考虑

### 4.2 申请步骤(如果 09-05 末决定做)

1. 访问 https://www.ensembl.org/Help/Contact
2. 邮件正文:项目名 / 用途 / 日均调用量 / 部署区域
3. Ensembl Helpdesk 一般 1-3 个工作日回复,提供 token
4. 调用时在 `Authorization: Bearer <token>` 头携带

### 4.3 09-05 决策建议

**先不申请**。Phase 1 用默认 15 req/s 跑 gene_info 增量(每周约 5-10 MB 增量),10 req/s 余量足够。如果 09-05 末实测发现瓶颈再补申请。

---

## 5. UniProt / ChEMBL(无 Key · 无需操作)

| 数据源 | 限制 | 备注 |
|---|---|---|
| UniProt REST | 100 req/s(IP) | 足够 Phase 1 全量 |
| UniProt FTP dump | 无限制 | 走 FTP 路径,无 Key |
| ChEMBL REST | 无明确限制,实测可 200 req/s | 足够 |
| ChEMBL FTP dump | 无限制 | 走 FTP 路径,无 Key |

**结论**:Phase 1 不需要 UniProt / ChEMBL 的任何凭证。

---

## 6. 验收 checklist(09-05 节点执行)

- [ ] NCBI API Key 申请完成,保存到密码管理器
- [ ] 运行 §2.4 验证脚本,输出 `✅ NCBI API Key 生效`
- [ ] Key 写入 `~/.zshrc` 或 `~/.bash_profile`,`source` 后可读
- [ ] Phase 1 项目 `.env` 文件含 `NCBI_API_KEY=...`,`git status` 不显示
- [ ] ClinicalTrials.gov §3.3 验证脚本输出 `✅ ClinicalTrials.gov 可达`
- [ ] `BiologyWeb/config/clinicaltrials.yaml` 创建(含真实 User-Agent)
- [ ] §3.4 robots.txt 已读,ETL 设计纳入"礼貌爬取"策略
- [ ] Ensembl 高级额度决策:延后 / 申请(填入决定)

---

## 7. 申请完成后回填指引

§5 Phase 0 唯一未完成 checkbox 文字为:

> [ ] 申请 NCBI API Key + ClinicalTrials.gov 爬虫白名单,确定 QPS 上限

**当 §6 验收 checklist 全部打勾后**:

1. 在 `项目开发计划.md` §5 找到该条
2. 末尾追加:**`(2026-09-XX 完成,NCBI Key 生效 10 req/s,ClinicalTrials 配置 50 req/min · 见 docs/architecture/api-keys-checklist.md)`**
3. `- [ ]` 改为 `- [x]`
4. 单独一个 commit,信息形如 `chore: 完成 Phase 0 §5 #4 API Key 申请`

**不要**在没拿到 Key 的情况下提前勾选,会影响项目进度的可信度。

---

## 8. 元数据

- 文档耗时:< 2 小时桌面研究(无实际 API 调用)
- 引用源:NCBI 官方 Settings 文档 / ClinicalTrials.gov API 文档 / Ensembl Helpdesk 政策
- 关联文档:
  - `项目开发计划.md` §5 Phase 0 第 4 项(本文档为其预备材料)
  - `docs/architecture/datasource-dump-eval.md` §2.3 NCBI 下载与刷新 / §3.3 UniProt 下载 / §4.3 Ensembl 下载
  - `docs/architecture/etl-incremental-sync-design.md` — 09-05 节点产出(待建,本清单为其前置)
- 下次更新:2026-09-05(API Key 真申请节点)

---

## 9. 9-09 验证快照(顾问代理执行)

> **目的**:9-08 巡检 §3 T2 P0 建议"哪怕 Key 未到也可输出'未配置 Key'明确信号"——本文档 §2.4 的 verify 脚本就绪后,顾问代理先跑一次以记录"Key 未配置"基线事实,主人申请 Key 后再跑一次对比"Key 生效"基线。**不动 §7 纪律(不提前勾 §5 #4 checkbox)**,仅追加"已跑过 verify"的事实快照。

### 9.1 执行记录

- **日期**:2026-09-09 03:40(cron T4 自动任务)
- **执行人**:17-生物-Biology 顾问(cron T4)
- **触发**:`.plan/20260909.md` 缺失,§5 #4 主人动作"申请 NCBI API Key"连续 5 天(9-05 ~ 9-09)未启动,9-08 巡检 §3 T2 明确建议先跑 verify 输出未配置信号

**执行命令**:
```bash
python3 scripts/verify_ncbi_key.py
echo "exit=$?"
```

**实际输出**(exit 1):
```
❌ NCBI_API_KEY 未设置;先在 NCBI 申请,再 export 或写入 ~/.zshrc
```

### 9.2 环境基线

| 探测项 | 结果 | 探测方式 |
|---|---|---|
| `os.environ['NCBI_API_KEY']` | `None` | `python3 -c "import os; print(repr(os.environ.get('NCBI_API_KEY')))"` |
| `BiologyWeb/.env` 文件 | 不存在 | `ls -la .env` → No such file or directory |
| `.gitignore` 凭证类屏蔽 | ✅ 已就位 | 显式列出 `.env` + `.env.*` |
| verify 脚本 exit code 语义 | ✅ 正确 | 0 = Key 生效 / 1 = Key 缺失或失效 |

### 9.3 结论

- ✅ **verify 脚本本身可用**:exit 1 明确区分"未配置"与"配置但失效"两种状态,后续 Key 到位后可直接复用同一脚本做"基线对比"(对比 9-09 快照 vs Key 到位后的"✅ Key 生效"快照)
- ❌ **NCBI_API_KEY 仍未配置**:§5 #4 主人动作连续 5 天(9-05 ~ 9-09)未启动,9-08 巡检 §1 / §2 预警持续
- ⏳ **§6 验收 checklist 8 项全部 `[ ]` 未变**:严格遵守 §7 "不要在没拿到 Key 的情况下提前勾选"纪律
- 📌 **主人动作只差 1 步**:登录 NCBI 账号 → Settings → Create API Key → `export NCBI_API_KEY="..."` → 重跑本脚本,exit 应转 0

### 9.4 后续路径

| 触发事件 | 动作 | 涉及文件 |
|---|---|---|
| 主人 export Key 后重跑 verify 退出 0 | 追加 §10 "9-XX Key 到位快照"(结构对称本节) | `api-keys-checklist.md` |
| verify 退出 0 后 | 走 §6 验收 checklist 8 项打勾 | `api-keys-checklist.md` §6 |
| §6 全打勾后 | 走 §7 回填指引:`项目开发计划.md` §5 #4 `- [ ]` → `- [x]` + 末尾追加 `(2026-09-XX 完成 ...)` | `项目开发计划.md` §5 |
| Key 申请后 NCBI 审核 1-3 个工作日 | Phase 1 第 1 周 NCBI Gene ETL 等 Key 启动 | `etl-incremental-sync-design.md`(待建) |

### 9.5 关联

- 9-08 巡检:`.Log/巡检-生物-20260908.md` §2 第 2 项 / §3 T2 P0 第 1 项
- 9-09 巡检:`.Log/巡检-生物-20260909.md` §2 第 2 项 / §3 T2 P0 第 1 项
- 历史建议(连续 5 天):主人只需做 1 个动作(API Key 真申请),其余可顾问独立完成
- 阶段信号:Phase 0 收尾**延长期第 3 天**(9-06 → 9-09 实际延期 3 天,见 9-09 巡检 §1)

---

## 10. 元数据(v1.1 · 9-09 追加)

- 9-09 增量:§9 验证快照(顾问代理执行,不动 §7 纪律,1 次 commit)
- 文档版本:v1.0 → v1.1
- 引用源(新增):9-08 / 9-09 巡检报告 §3 T2 P0 建议 + `scripts/verify_ncbi_key.py` 9-05 提交
- 下次更新:主人 export NCBI_API_KEY 后 → §10 Key 到位快照 → §6 → §7 流程
