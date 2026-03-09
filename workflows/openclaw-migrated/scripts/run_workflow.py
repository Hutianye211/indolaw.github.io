#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd):
    print("$", " ".join(cmd))
    p = subprocess.run(cmd)
    if p.returncode != 0:
        raise SystemExit(p.returncode)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Openclaw workflow migrated runner")
    parser.add_argument("--skip-brave", action="store_true")
    parser.add_argument("--skip-hkex", action="store_true")
    parser.add_argument("--skip-cninfo", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    parser.add_argument("--brave-count", type=int, default=10)
    parser.add_argument("--brave-country", default="cn")
    parser.add_argument("--brave-search-lang", default="zh-hans")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--cninfo-max-pages", type=int, default=5)
    parser.add_argument("--hkex-max-companies", type=int, default=120)
    args = parser.parse_args()

    load_env_file(ROOT / ".env")

    # Layer-1/2: Brave recruitment + tender search.
    brave_key = os.getenv("BRAVE_API_KEY", "")
    if not brave_key:
        print("[warn] BRAVE_API_KEY missing: recruitment/tender search layer is not enabled.")

    py = sys.executable

    if not args.skip_brave and brave_key:
        run(
            [
                py,
                str(SCRIPTS / "brave_search_signals.py"),
                "--count",
                str(args.brave_count),
                "--country",
                args.brave_country,
                "--search-lang",
                args.brave_search_lang,
            ]
        )

    if not args.skip_cninfo:
        cmd = [py, str(SCRIPTS / "cninfo_announcements.py")]
        if args.start_date:
            cmd += ["--start-date", args.start_date]
        if args.end_date:
            cmd += ["--end-date", args.end_date]
        cmd += ["--max-pages", str(args.cninfo_max_pages)]
        run(cmd)

    if not args.skip_hkex:
        run([py, str(SCRIPTS / "hkex_screener.py"), "--max-companies", str(args.hkex_max_companies)])

    if not args.skip_report:
        run([py, str(SCRIPTS / "generate_markdown_report.py")])


if __name__ == "__main__":
    main()
