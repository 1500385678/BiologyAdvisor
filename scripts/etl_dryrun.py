#!/usr/bin/env python3
"""ETL DDL dry-run · 静态解析 etl_schema.sql 输出结构化报告

依据:`docs/architecture/etl-incremental-sync-design.md` §3 / §7
      `app/db/etl_schema.sql`(9-11 cron T4 落地 `e10e779`)
      `app/db/README.md`(9-12 cron T5 落地 `5abf832`)
节点:Phase 1 ETL 启动期(2026-09-14 cron T4)

特性:
- 零外部依赖(stdlib only),与 scripts/verify_*.py 一致
- 静态解析 DDL,不连 PostgreSQL,不引 psycopg2(留 Phase 1 实施期决策)
- 输出 3 表 / 字段数 / 索引数 / 外键数 / 部分索引数 汇总报告
- 给 §6 Phase 1 第 1 项"完成 5 个核心数据源的 ETL 流水线"提供 DDL 侧自检基线
- 退出码 0 = 解析成功,1 = 文件缺失 / 解析失败

用法:
    python3 scripts/etl_dryrun.py
    python3 scripts/etl_dryrun.py --schema app/db/etl_schema.sql
    python3 scripts/etl_dryrun.py --schema /path/to/etl_schema.sql --quiet
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 默认 DDL 路径:相对仓库根(脚本从仓库根或 scripts/ 目录跑都能找到)
DEFAULT_SCHEMA = "app/db/etl_schema.sql"
REPO_ROOT_HINT = Path(__file__).resolve().parent.parent

# DDL 解析用正则(简版,够用即可,不追求完整 SQL 解析)
TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*;",
    re.DOTALL | re.IGNORECASE,
)
INDEX_RE = re.compile(
    r"CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)",
    re.IGNORECASE,
)
FOREIGN_KEY_RE = re.compile(r"REFERENCES\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", re.IGNORECASE)
PARTIAL_INDEX_RE = re.compile(r"\bWHERE\b", re.IGNORECASE)


def parse_schema(schema_path: Path) -> dict:
    """解析 etl_schema.sql,返回结构化报告。

    返回字典:
      {
        "tables": [{"name": str, "fields": int, "primary_key": str|None}, ...],
        "indexes": int,
        "partial_indexes": int,
        "foreign_keys": [{"table": str, "references": str}, ...],
        "table_total": int,
        "field_total": int,
      }
    """
    if not schema_path.exists():
        raise FileNotFoundError(f"DDL 文件不存在: {schema_path}")

    text = schema_path.read_text(encoding="utf-8")

    tables: list[dict] = []
    for match in TABLE_RE.finditer(text):
        name, body = match.group(1), match.group(2)
        # 字段数:按顶层逗号切(忽略括号内逗号,简化处理)
        depth = 0
        field_count = 1  # 至少有 1 个字段
        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif ch == "," and depth == 0:
                field_count += 1
        # PRIMARY KEY 列(粗略抓第一处 "PRIMARY KEY" 前的字段名)
        pk_match = re.search(r"(\b[a-zA-Z_][a-zA-Z0-9_]*)\s+[A-Z][A-Z0-9_()]*\s+PRIMARY\s+KEY", body, re.IGNORECASE)
        primary_key = pk_match.group(1) if pk_match else None
        tables.append({"name": name, "fields": field_count, "primary_key": primary_key})

    indexes = len(INDEX_RE.findall(text))
    partial = len(PARTIAL_INDEX_RE.findall(text))
    # 单层 finditer(避免对每张表重复扫描全文,导致 REFERENCES 计数 = 3 × 实际 = 3)
    foreign_keys = [
        {"references": fk.group(1)}
        for fk in FOREIGN_KEY_RE.finditer(text)
    ]

    return {
        "tables": tables,
        "indexes": indexes,
        "partial_indexes": partial,
        "foreign_keys": foreign_keys,
        "table_total": len(tables),
        "field_total": sum(t["fields"] for t in tables),
    }


def render_report(report: dict, schema_path: Path, quiet: bool = False) -> str:
    """格式化报告为可读文本。quiet=True 只输出关键数字行。"""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append(f"ETL DDL dry-run · {schema_path}")
    lines.append("=" * 72)
    lines.append("")

    lines.append(f"📊 总览")
    lines.append(f"  表数:     {report['table_total']}")
    lines.append(f"  字段总数: {report['field_total']}")
    lines.append(f"  索引数:   {report['indexes']}")
    lines.append(f"  部分索引: {report['partial_indexes']}")
    lines.append(f"  外键数:   {len(report['foreign_keys'])}")
    lines.append("")

    if not quiet:
        lines.append("📋 表清单")
        for t in report["tables"]:
            pk = f" · PK={t['primary_key']}" if t["primary_key"] else ""
            lines.append(f"  · {t['name']:<20s} 字段数={t['fields']}{pk}")
        lines.append("")

        if report["foreign_keys"]:
            lines.append("🔗 外键关系")
            for fk in report["foreign_keys"]:
                lines.append(f"  · 某表.run_id → {fk['references']}.id (ON DELETE CASCADE)")
            lines.append("")

    lines.append("=" * 72)
    lines.append("✅ DDL 解析成功 · 零依赖 · 无 DB 连接")
    lines.append("   下一步:Phase 1 实施期 psql -f 应用 DDL,然后跑真实 ETL 写入")
    lines.append("=" * 72)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL DDL dry-run · 静态解析 etl_schema.sql")
    parser.add_argument(
        "--schema",
        default=DEFAULT_SCHEMA,
        help=f"DDL 文件路径(默认: {DEFAULT_SCHEMA},相对仓库根)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="只输出总览数字行,不打印表清单和外键关系",
    )
    args = parser.parse_args()

    schema_path = Path(args.schema)
    if not schema_path.is_absolute():
        # 优先相对脚本所在仓库根,其次相对 cwd
        candidate = REPO_ROOT_HINT / schema_path
        if candidate.exists():
            schema_path = candidate

    try:
        report = parse_schema(schema_path)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        print(f"   提示:从仓库根跑,或用 --schema 指定绝对路径", file=sys.stderr)
        return 1
    except re.error as e:
        print(f"❌ 正则解析失败: {e}", file=sys.stderr)
        return 1

    print(render_report(report, schema_path, quiet=args.quiet))
    return 0


if __name__ == "__main__":
    sys.exit(main())
