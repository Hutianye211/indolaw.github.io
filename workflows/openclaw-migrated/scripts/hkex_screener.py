#!/usr/bin/env python3
import argparse
import datetime as dt
import io
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import urllib.request
from urllib.error import URLError

try:
    from pdfminer.high_level import extract_text as pdf_extract
except ImportError:
    pdf_extract = None

DEFAULT_KW = ["越南", "印尼", "印度尼西亞", "新加坡", "馬來西亞", "印度尼西亚", "马来西亚"]
HKEX_JSON_ACTIVE_MAIN_C = "https://www1.hkexnews.hk/ncms/json/eds/appactive_app_sehk_c.json"


def fetch_bytes(url: str, ua: str, timeout: int = 20) -> Optional[bytes]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None


def fetch_html(url: str, ua: str) -> Optional[str]:
    raw = fetch_bytes(url, ua=ua, timeout=20)
    if not raw:
        return None
    for enc in ("utf-8", "big5", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", "replace")


def parse_htm(html: str, base_dir: str) -> Tuple[str, Dict[str, str]]:
    comp_m = re.search(r'type="compName"[^>]*>\s*<b>([^<]+)</b>', html)
    company = comp_m.group(1).strip() if comp_m else "Unknown"
    chapters: Dict[str, str] = {}
    for m in re.finditer(r'href="([^"]+\.pdf)"[^>]*target="_blank">([^<]+)<', html):
        href, text = m.group(1), m.group(2).strip()
        full = href if href.startswith("http") else (base_dir + href)
        chapters[text] = full
    return company, chapters


def scan_pdf_kw(pdf_url: str, keywords: List[str], ua: str, timeout: int = 25) -> List[dict]:
    if pdf_extract is None:
        print("[error] missing dependency: pdfminer.six")
        print("[hint] 运行: pip install -r requirements.txt")
        raise SystemExit(2)
    raw = fetch_bytes(pdf_url, ua=ua, timeout=timeout)
    if not raw:
        return []
    try:
        text = pdf_extract(io.BytesIO(raw))
    except Exception:
        return []

    hits = []
    for kw in keywords:
        if kw in text:
            idx = text.find(kw)
            snippet = text[max(0, idx - 80): idx + 250].replace("\n", " ").strip()
            hits.append({"kw": kw, "snippet": snippet[:350]})
    return hits


def read_urls(path: Path) -> List[str]:
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def fetch_dynamic_urls(
    json_url: str,
    ua: str,
    require_coordinator_notice: bool = True,
    max_companies: int = 120,
) -> List[str]:
    req = urllib.request.Request(json_url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    apps = payload.get("app") if isinstance(payload, dict) else []
    if not isinstance(apps, list):
        return []

    rows = []
    for item in apps:
        if not isinstance(item, dict):
            continue
        ls = item.get("ls") if isinstance(item.get("ls"), list) else []
        has_coordinator = any("整體協調人公告" in (x.get("nS1") or "") for x in ls if isinstance(x, dict))
        app_links = [x.get("u2") for x in ls if isinstance(x, dict) and "申請版本" in (x.get("nF") or "") and x.get("u2")]
        if not app_links:
            continue
        if require_coordinator_notice and not has_coordinator:
            continue

        date_text = item.get("d") or ""
        rows.append(
            {
                "date_text": date_text,
                "u2": app_links[0],
            }
        )

    def parse_date_value(s: str) -> Tuple[int, int, int]:
        m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s or "")
        if not m:
            return (0, 0, 0)
        dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return (yyyy, mm, dd)

    rows.sort(key=lambda r: parse_date_value(r["date_text"]), reverse=True)

    out = []
    for row in rows[:max_companies]:
        u2 = row["u2"]
        if u2.startswith("http"):
            out.append(u2)
        else:
            out.append("https://www1.hkexnews.hk/app/" + u2.lstrip("/"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="HKEX two-stage screener migrated from Openclaw")
    parser.add_argument("--urls-file", type=Path, default=Path(__file__).resolve().parents[1] / "seed_hkex_urls.txt")
    parser.add_argument("--dynamic-json-url", default=HKEX_JSON_ACTIVE_MAIN_C)
    parser.add_argument("--use-dynamic", action="store_true", default=True)
    parser.add_argument("--fallback-to-seed", action="store_true", default=True)
    parser.add_argument("--max-companies", type=int, default=120)
    parser.add_argument("--require-coordinator-notice", action="store_true", default=True)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "output")
    parser.add_argument("--ua", default="Mozilla/5.0 (Openclaw-Migrated-Workflow)")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KW)
    args = parser.parse_args()

    urls: List[str] = []
    if args.use_dynamic:
        try:
            urls = fetch_dynamic_urls(
                json_url=args.dynamic_json_url,
                ua=args.ua,
                require_coordinator_notice=args.require_coordinator_notice,
                max_companies=args.max_companies,
            )
            print(f"[dynamic] loaded {len(urls)} urls from HKEX active JSON")
        except URLError as e:
            print(f"[warn] dynamic HKEX source unavailable: {e}")
        except Exception as e:
            print(f"[warn] dynamic HKEX source parse failed: {e}")

    if not urls and args.fallback_to_seed:
        urls = read_urls(args.urls_file)
        print(f"[fallback] using seed urls: {len(urls)}")

    candidates: List[Tuple[str, str, Dict[str, str]]] = []

    print(f"=== 阶段一：概要 PDF 预筛（{len(urls)} 家）===")
    for i, url in enumerate(urls, start=1):
        base_dir = url.rsplit("/", 1)[0] + "/"
        html = fetch_html(url, ua=args.ua)
        if not html:
            print(f"[{i}] 页面拉取失败: {url}")
            continue

        company, chapters = parse_htm(html, base_dir)
        summary_url = next((v for k, v in chapters.items() if k.strip() in ("概要", "業務概要")), None)

        if not summary_url:
            print(f"[{i}] {company} -> 无概要，直接入候选")
            candidates.append((url, company, chapters))
            continue

        summary_hits = scan_pdf_kw(summary_url, keywords=args.keywords, ua=args.ua, timeout=15)
        if summary_hits:
            kw = sorted({h["kw"] for h in summary_hits})
            print(f"[{i}] {company} -> 概要命中 {kw}")
            candidates.append((url, company, chapters))
        else:
            print(f"[{i}] {company} -> 概要无命中")

    print(f"\n预筛候选: {len(candidates)} 家")
    print("=== 阶段二：精读 风险因素 + 未来计划 ===")

    results = []
    for url, company, chapters in candidates:
        risk_url = next((v for k, v in chapters.items() if "風險因素" in k), None)
        future_url = next((v for k, v in chapters.items() if "未來計劃" in k), None)

        all_hits = []
        for chapter_name, pdf_url in (("風險因素", risk_url), ("未來計劃及用途", future_url)):
            if not pdf_url:
                continue
            hits = scan_pdf_kw(pdf_url, keywords=args.keywords, ua=args.ua, timeout=30)
            for hit in hits:
                hit["chapter"] = chapter_name
            all_hits.extend(hits)

        if all_hits:
            results.append({"company": company, "url": url, "hits": all_hits})
            print(f"命中: {company} ({len(all_hits)} 条)")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out = args.output_dir / f"hkex_results_{dt.date.today().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成: {len(results)} 家命中，结果已写入 {out}")


if __name__ == "__main__":
    main()
