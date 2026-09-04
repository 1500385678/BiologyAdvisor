#!/usr/bin/env python3
"""验证 NCBI API Key 是否生效 · 09-05 节点由人工执行

依据:`docs/architecture/api-keys-checklist.md` §2.4
Phase 0 收尾期(2026-09-05)Phase 0 §5 #4 节点产出

NCBI API Key 申请需人工(登录 NCBI 账号 → Settings → Create API Key),
agent 无法代劳,所以本脚本是"申请后一键验证"工具,留给用户自己跑。

特性:
- 读 NCBI_API_KEY 环境变量(Phase 1 实施期从 .env 加载,本阶段直接 env)
- stdlib urllib 实现,零依赖
- 退出码 0 = Key 生效,1 = Key 缺失 / 失效 / 网络错误

预期输出:`✅ NCBI API Key 生效,响应时间 ~200-400 ms`

用法:
    # 1. 在 NCBI 申请 Key:https://www.ncbi.nlm.nih.gov/account/settings/
    # 2. 写入 ~/.zshrc 或临时 export:
    export NCBI_API_KEY="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    # 3. 运行验证
    python3 scripts/verify_ncbi_key.py
    python3 scripts/verify_ncbi_key.py --db gene
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi"
DEFAULT_DB = "gene"
DEFAULT_TIMEOUT_S = 10
PLACEHOLDER = "在此填入 Key"


def check_key(
    api_key: str,
    base: str = DEFAULT_BASE,
    db: str = DEFAULT_DB,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> bool:
    """真发请求验证 NCBI API Key。

    返回 True 表示 Key 生效,False 表示失败。
    """
    if not api_key or api_key == PLACEHOLDER:
        print("❌ NCBI_API_KEY 未设置;先在 NCBI 申请,再 export 或写入 ~/.zshrc", file=sys.stderr)
        return False

    params = {"db": db, "api_key": api_key, "retmode": "json"}
    url = f"{base}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = resp.status
            body = resp.read()
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code} {e.reason} (db={db!r})", file=sys.stderr)
        if e.code == 429:
            print("   提示:429 = 触发速率限制,Key 可能仍有效但被节流,稍后重试", file=sys.stderr)
        elif e.code in (400, 401, 403):
            print("   提示:Key 异常或 db 名错误;检查 NCBI_API_KEY 字符串", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"❌ URL 错误: {e.reason}", file=sys.stderr)
        return False
    dt_ms = (time.time() - t0) * 1000

    if status != 200:
        print(f"❌ 状态码 {status},预期 200", file=sys.stderr)
        return False

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        return False

    # 正常响应结构:{"einforesult": {"dbinfo": [...]}}
    if "einforesult" in data and "dbinfo" in data["einforesult"]:
        einfo = data["einforesult"]["dbinfo"][0] if isinstance(data["einforesult"]["dbinfo"], list) else data["einforesult"]["dbinfo"]
        dbname = einfo.get("dbname", db)
        print(f"✅ NCBI API Key 生效 · db={dbname} · 响应时间 {dt_ms:.0f} ms")
        return True

    # E-utilities 在 Key 失效时也可能返回结构化错误
    err = data.get("error") or data.get("einforesult", {}).get("error")
    if err:
        print(f"❌ NCBI 返回错误: {err}", file=sys.stderr)
        return False

    print(f"❌ 响应结构异常,无法确认 Key 生效:{json.dumps(data)[:200]}", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 NCBI API Key 是否生效")
    parser.add_argument("--api-key", default=os.environ.get("NCBI_API_KEY"), help="API Key(默认读 NCBI_API_KEY 环境变量)")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"测试数据库(默认: {DEFAULT_DB})")
    parser.add_argument("--base", default=DEFAULT_BASE, help="eutils 端点")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="请求超时秒数")
    args = parser.parse_args()

    ok = check_key(
        api_key=args.api_key or "",
        base=args.base,
        db=args.db,
        timeout_s=args.timeout,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
