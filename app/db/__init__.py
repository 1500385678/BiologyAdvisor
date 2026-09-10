"""BiologyAdvisor · DB 子包

Phase 0 收尾延长期(2026-09-11)由 cron T4 节点产出。

目的:
- 集中放置 ETL 状态表 / 业务表的 DDL 文件
- Phase 1 ETL 实施期(预计 9-13 ~ 9-25)按本子包内文件直接 psql 落地
- 不在本子包写 Python ORM(Pydantic 校验放 app/services,SQLAlchemy 留 Phase 1 决策)

当前文件:
- etl_schema.sql  · etl_state / etl_run_log / etl_quarantine 三表 DDL + 索引
                    来源:`docs/architecture/etl-incremental-sync-design.md` §3 / §7

不做什么(明确边界):
- 不连 PostgreSQL(Phase 1 实施期再上 SQLAlchemy / asyncpg)
- 不写迁移工具(Alembic 留 Phase 1 决策)
- 不引入种子数据(种子由 ETL 真实跑产出)
"""
