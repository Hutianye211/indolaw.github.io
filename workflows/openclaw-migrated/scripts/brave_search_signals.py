#!/usr/bin/env python3
import argparse
import datetime as dt
import gzip
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List
from urllib.error import HTTPError, URLError

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

RECRUITMENT_QUERIES = [
    '"印尼" site:liepin.com 总经理 OR 厂长 化工 OR 新能源 OR 冶金 OR 新材料',
    '"印度尼西亚" site:liepin.com 建厂 OR 工厂 OR 海外项目',
    '"东南亚" 建厂 厂长 招聘 化工 OR 新能源 OR 冶金 OR 新材料 2026',
    '"印尼" "海外工厂总经理" OR "印尼总经理" OR "印尼厂长" 招聘',
    '"东南亚总经理" OR "海外投资总监" 制造 OR 化工 OR 新能源 招聘',
    'site:linkedin.com "Indonesia" "General Manager" "factory" China 2026',
]

TENDER_QUERIES = [
    '东南亚 OR 印尼 OR 越南 可行性研究 OR 工艺设计 OR EPC 化工 OR 新材料 OR 冶金',
    '印度尼西亚 新建工厂 招标 OR 采购 2025 OR 2026',
]


def brave_search(api_key: str, query: str, count: int, country: str, search_lang: str) -> Dict:
    params = {
        "q": query,
        "count": str(count),
        "country": country,
        "search_lang": search_lang,
    }
    url = f"{BRAVE_ENDPOINT}?{urllib.parse.urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
        "User-Agent": "Mozilla/5.0 (Openclaw-Migrated-Workflow)",
    }

    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        encoding = (resp.headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def extract_web_results(payload: Dict) -> List[Dict]:
    web = payload.get("web") if isinstance(payload, dict) else None
    results = web.get("results") if isinstance(web, dict) else []
    if not isinstance(results, list):
        return []

    out: List[Dict] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        profile = row.get("profile") if isinstance(row.get("profile"), dict) else {}
        out.append(
            {
                "title": row.get("title"),
                "url": row.get("url"),
                "description": row.get("description"),
                "source": profile.get("long_name") or profile.get("name"),
                "age": row.get("age"),
                "language": row.get("language"),
            }
        )
    return out


def run_group(
    api_key: str,
    group_name: str,
    queries: List[str],
    count: int,
    country: str,
    search_lang: str,
) -> Dict:
    items = []
    for idx, q in enumerate(queries, start=1):
        try:
            data = brave_search(api_key=api_key, query=q, count=count, country=country, search_lang=search_lang)
            rows = extract_web_results(data)
            items.append({"query": q, "result_count": len(rows), "results": rows})
            print(f"[{group_name} {idx}/{len(queries)}] ok: {len(rows)} results")
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:400]
            except Exception:
                body = "<no body>"
            items.append({"query": q, "error": f"HTTP {e.code}", "details": body, "results": []})
            print(f"[{group_name} {idx}/{len(queries)}] error: HTTP {e.code}")
        except URLError as e:
            items.append({"query": q, "error": f"URLError: {e}", "results": []})
            print(f"[{group_name} {idx}/{len(queries)}] error: {e}")

    # URL 去重汇总
    seen = set()
    merged = []
    for item in items:
        for row in item.get("results", []):
            url = row.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            merged.append(row)

    return {
        "group": group_name,
        "queries": items,
        "unique_results": merged,
        "unique_result_count": len(merged),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Brave Search layer for recruitment + tender signals")
    parser.add_argument("--api-key", default=os.getenv("BRAVE_API_KEY", ""))
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--country", default="cn")
    parser.add_argument("--search-lang", default="zh-hans")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "output")
    args = parser.parse_args()

    if not args.api_key:
        print("[error] BRAVE_API_KEY is required.")
        raise SystemExit(2)

    recruitment = run_group(
        api_key=args.api_key,
        group_name="recruitment",
        queries=RECRUITMENT_QUERIES,
        count=args.count,
        country=args.country,
        search_lang=args.search_lang,
    )
    tender = run_group(
        api_key=args.api_key,
        group_name="tender",
        queries=TENDER_QUERIES,
        count=args.count,
        country=args.country,
        search_lang=args.search_lang,
    )

    result = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "country": args.country,
        "search_lang": args.search_lang,
        "count": args.count,
        "recruitment": recruitment,
        "tender": tender,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"brave_signals_{dt.date.today().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"done: recruitment_unique={recruitment['unique_result_count']}, "
        f"tender_unique={tender['unique_result_count']}"
    )
    print(f"output: {out}")


if __name__ == "__main__":
    main()
