#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.error import URLError

CNINFO_HOME = "http://www.cninfo.com.cn"
CNINFO_API = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

DEFAULT_REGION_KW = ["东南亚", "印尼", "印度尼西亚", "Indonesia", "越南", "泰国", "马来西亚"]
DEFAULT_SIGNAL_KW = ["境外投资", "对外投资", "设立子公司", "建设项目", "产能扩张"]
DEFAULT_EXCLUDE_KW = ["股权转让", "减持", "仲裁", "诉讼", "清算"]


def _strip_em(text: str) -> str:
    return re.sub(r"</?em>", "", text or "", flags=re.IGNORECASE)


def _unique_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def request_announcements(page_num: int, page_size: int, start: str, end: str, searchkey: str) -> Dict:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    headers = {"User-Agent": "Mozilla/5.0 (Openclaw-Migrated-Workflow)"}
    opener.open(urllib.request.Request(CNINFO_HOME, headers=headers), timeout=20)

    payload = {
        "pageNum": page_num,
        "pageSize": page_size,
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": searchkey,
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"{start}~{end}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }

    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(CNINFO_API, data=data, headers=headers, method="POST")
    with opener.open(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def request_announcements_with_opener(
    opener: urllib.request.OpenerDirector,
    page_num: int,
    page_size: int,
    start: str,
    end: str,
    searchkey: str,
) -> Dict:
    headers = {"User-Agent": "Mozilla/5.0 (Openclaw-Migrated-Workflow)"}
    payload = {
        "pageNum": page_num,
        "pageSize": page_size,
        "column": "szse",
        "tabName": "fulltext",
        "plate": "",
        "stock": "",
        "searchkey": searchkey,
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"{start}~{end}",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(CNINFO_API, data=data, headers=headers, method="POST")
    with opener.open(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def flatten_results(raw: Dict, exclude_kw: List[str], source_query: str) -> List[Dict]:
    out = []
    anns = raw.get("announcements") or []
    if not isinstance(anns, list):
        return out

    for row in anns:
        if not isinstance(row, dict):
            continue
        title = _strip_em(row.get("announcementTitle", ""))
        if any(kw in title for kw in exclude_kw):
            continue
        out.append(
            {
                "secCode": row.get("secCode"),
                "secName": row.get("secName"),
                "title": title,
                "publishTime": row.get("announcementTime"),
                "detailUrl": f"https://static.cninfo.com.cn/{row.get('adjunctUrl', '').lstrip('/')}",
                "announcementId": row.get("announcementId"),
                "sourceQuery": source_query,
            }
        )
    return out


def keep_signal_region_intersection(rows: List[Dict], region_kw: List[str], signal_kw: List[str]) -> List[Dict]:
    out = []
    for row in rows:
        title = row.get("title", "")
        matched_regions = [kw for kw in region_kw if kw and kw in title]
        matched_signals = [kw for kw in signal_kw if kw and kw in title]
        if not matched_regions or not matched_signals:
            continue
        row["matchedRegions"] = matched_regions
        row["matchedSignals"] = matched_signals
        out.append(row)
    return out


def dedupe_rows(rows: List[Dict]) -> List[Dict]:
    out = []
    seen = set()
    for row in rows:
        key = (row.get("announcementId"), row.get("detailUrl"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def run_multi_query(
    start_page_num: int,
    page_size: int,
    max_pages: int,
    start: str,
    end: str,
    region_keywords: List[str],
    signal_keywords: List[str],
    exclude_keywords: List[str],
) -> Tuple[List[Dict], List[Dict]]:
    query_terms = _unique_keep_order(signal_keywords + region_keywords)
    all_rows: List[Dict] = []
    stats: List[Dict] = []

    for q in query_terms:
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        headers = {"User-Agent": "Mozilla/5.0 (Openclaw-Migrated-Workflow)"}
        opener.open(urllib.request.Request(CNINFO_HOME, headers=headers), timeout=20)

        fetched_total = 0
        total_announcement = None
        has_error = None
        error_code = None

        for page_num in range(start_page_num, start_page_num + max_pages):
            raw = request_announcements_with_opener(
                opener=opener,
                page_num=page_num,
                page_size=page_size,
                start=start,
                end=end,
                searchkey=q,
            )
            rows = flatten_results(raw, exclude_kw=exclude_keywords, source_query=q)
            all_rows.extend(rows)
            anns = raw.get("announcements") or []
            page_len = len(anns) if isinstance(anns, list) else 0
            fetched_total += page_len
            total_announcement = raw.get("totalAnnouncement")
            has_error = raw.get("hasError")
            error_code = raw.get("errorCode")
            if page_len == 0:
                break
            total_pages = raw.get("totalpages")
            if isinstance(total_pages, int) and page_num >= total_pages:
                break

        stats.append(
            {
                "query": q,
                "fetched": fetched_total,
                "totalAnnouncement": total_announcement,
                "hasError": has_error,
                "errorCode": error_code,
            }
        )

    deduped = dedupe_rows(all_rows)
    filtered = keep_signal_region_intersection(deduped, region_kw=region_keywords, signal_kw=signal_keywords)
    filtered.sort(key=lambda x: x.get("publishTime") or 0, reverse=True)
    return filtered, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Cninfo announcement scraper migrated from Openclaw")
    parser.add_argument("--start-date", default=(dt.date.today() - dt.timedelta(days=30)).isoformat())
    parser.add_argument("--end-date", default=dt.date.today().isoformat())
    parser.add_argument("--page-num", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--region-keywords", nargs="*", default=DEFAULT_REGION_KW)
    parser.add_argument("--signal-keywords", nargs="*", default=DEFAULT_SIGNAL_KW)
    parser.add_argument("--exclude-keywords", nargs="*", default=DEFAULT_EXCLUDE_KW)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "output")
    args = parser.parse_args()

    try:
        rows, stats = run_multi_query(
            start_page_num=args.page_num,
            page_size=args.page_size,
            max_pages=args.max_pages,
            start=args.start_date,
            end=args.end_date,
            region_keywords=args.region_keywords,
            signal_keywords=args.signal_keywords,
            exclude_keywords=args.exclude_keywords,
        )
    except URLError as e:
        print(f"[error] cninfo network request failed: {e}")
        print("[hint] 请确认当前环境可访问外网后重试。")
        raise SystemExit(2)
    except Exception as e:
        print(f"[error] cninfo request failed: {e}")
        raise SystemExit(2)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"cninfo_results_{dt.date.today().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"query terms: {[s['query'] for s in stats]}")
    for s in stats:
        print(
            f"  - {s['query']}: fetched={s['fetched']}, totalAnnouncement={s['totalAnnouncement']}, "
            f"hasError={s['hasError']}, errorCode={s['errorCode']}"
        )
    print(f"kept_after_intersection: {len(rows)}")
    print(f"output: {out}")


if __name__ == "__main__":
    main()
