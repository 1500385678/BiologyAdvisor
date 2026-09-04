#!/usr/bin/env python3
"""验证 ClinicalTrials.gov API 可达性 · 09-05 节点直接运行

依据:`docs/architecture/api-keys-checklist.md` §3.3
Phase 0 收尾期(2026-09-05)Phase 0 §5 #4 节点产出

特性:
- 用 stdlib urllib,不引入 requests/pyyaml 依赖(Phase 0 收尾期最小集)
- 真发请求,验证 UA 配置 + 速率限制 + 端点可达
- 退出码 0 = 通过,1 = 失败,便于 CI / 后续 ETL 流水线串联

用法:
    python3 scripts/verify_clinicaltrials.py
    python3 scripts/verify_clinicaltrials.py --query "EGFR AND lung" --page-size 5
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# 默认配置:与 config/clinicaltrials.yaml 对齐(Phase 1 改用 config loader)
DEFAULT_BASE_URL = "https://clinicaltrials.gov/api/v2"
DEFAULT_USER_AGENT = "BiologyAdvisor/0.1 (mailto:dev@biologyadvisor.cn)"
DEFAULT_QUERY = "EGFR"
DEFAULT_PAGE_SIZE = 5
DEFAULT_TIMEOUT_S = 10


def check_reachability(
    base_url: str = DEFAULT_BASE_URL,
    user_agent: str = DEFAULT_USER_AGENT,
    query: str = DEFAULT_QUERY,
    page_size: int = DEFAULT_PAGE_SIZE,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> bool:
    """真发请求验证 ClinicalTrials.gov API。

    返回 True 表示通过,False 表示失败。
    """
    url = f"{base_url.rstrip('/')}/studies"
    params = {"query.term": query, "pageSize": str(page_size)}
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full_url, headers={"User-Agent": user_agent})

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = resp.status
            body = resp.read()
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code} {e.reason} (查询={query!r})", file=sys.stderr)
        return False
    except urllib.error.URLError as e:
        print(f"❌ URL 错误: {e.reason} (查询={query!r})", file=sys.stderr)
        return False
    dt_ms = (time.time() - t0) * 1000

    if status != 200:
        print(f"❌ 状态码 {status},预期 200 (查询={query!r})", file=sys.stderr)
        return False

    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        print(f"❌ JSON 解析失败: {e}", file=sys.stderr)
        return False

    studies = data.get("studies", [])
    n = len(studies)
    if n == 0:
        print(f"⚠️ ClinicalTrials.gov 可达但 {query!r} 返回 0 条(可能查询过窄或服务异常)")
        return False

    # 抽样第一条显示 NCT ID + 简要标题(便于人工 review)
    first = studies[0]
    nct_id = (
        first.get("protocolSection", {})
        .get("identificationModule", {})
        .get("nctId", "?")
    )
    print(f"✅ ClinicalTrials.gov 可达 · 查询={query!r} · 返回 {n} 条 · 首条 NCT={nct_id} · 耗时 {dt_ms:.0f} ms")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 ClinicalTrials.gov API 可达性")
    parser.add_argument("--query", default=DEFAULT_QUERY, help=f"查询关键词(默认: {DEFAULT_QUERY!r})")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE, help=f"返回条数(默认: {DEFAULT_PAGE_SIZE})")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API 根 URL")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent 字符串")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="请求超时秒数")
    args = parser.parse_args()

    ok = check_reachability(
        base_url=args.base_url,
        user_agent=args.user_agent,
        query=args.query,
        page_size=args.page_size,
        timeout_s=args.timeout,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
