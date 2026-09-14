# BiologyAdvisor

> 17-生物-Biology 行业 Web 项目 · 内部代号 BiologyAdvisor

## 项目说明
基于张勇的 36 行业架构,BiologyAdvisor 是 生物-Biology 行业的 Web 端顾问产品。

## 同步
- GitHub: https://github.com/1500385678/BiologyAdvisor
- Gitee: https://gitee.com/architectzy/BiologyAdvisor

## 自动化
- T4 每日 02:00 检查项目并更新开发计划
- T5 每日 03:00 完成小步开发并 commit + push

## 自检基线 · DDL dry-run

> Phase 1 ETL 启动期零依赖自检工具 · 不连数据库 · 不引 psycopg2

ETL 流水线正式跑通前,先用 `scripts/etl_dryrun.py` 静态解析 DDL,验证表结构、字段数、索引数、外键数符合设计预期。

**入口**:`scripts/etl_dryrun.py`(2026-09-14 cron T4 落地 `4a9ee2e`)

**特性**:
- 零外部依赖(stdlib only,与 `scripts/verify_*.py` 一致)
- 静态解析 `app/db/etl_schema.sql`(9-11 cron T4 落地 `e10e779`)
- 输出 3 表 / 字段数 / 索引数 / 部分索引数 / 外键数 汇总报告
- 退出码 0 = 解析成功,1 = 文件缺失 / 解析失败

**用法**:

```bash
# 从仓库根跑(默认解析 app/db/etl_schema.sql)
python3 scripts/etl_dryrun.py

# 自定义 DDL 路径
python3 scripts/etl_dryrun.py --schema /path/to/etl_schema.sql

# 只输出关键数字行(CI / 巡检友好)
python3 scripts/etl_dryrun.py --quiet
```

**设计锚点**:
- 数据契约:[`docs/architecture/etl-incremental-sync-design.md`](docs/architecture/etl-incremental-sync-design.md) §3 / §7
- 应用说明:[`app/db/README.md`](app/db/README.md)(9-12 cron T5 落地 `5abf832`)
- DDL 三表定义:[`app/db/etl_schema.sql`](app/db/etl_schema.sql)(etl_state / etl_run_log / etl_quarantine)

**Phase 1 §6 第 1 项"完成 5 个核心数据源的 ETL 流水线"启动三信号**:
1. ETL 增量同步设计 v1.0(9-10 `2898693` 闭合 §8.3 5 TODO)
2. ETL 三表 DDL + 应用说明(9-11 + 9-12 双 commit)
3. ETL DDL dry-run 自检基线(9-14 + 本 README 文档化入口)

> 三信号后:实跑 5 源 ETL → 增量同步 → 监控告警 → checkbox 勾选(Phase 1 实施期决议)
