#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def today_str() -> str:
    return dt.date.today().strftime("%Y%m%d")


def md_escape(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def infer_company_from_title(title: str) -> str:
    if not title:
        return "待人工确认"
    clean = re.sub(r"【.*?】", "", title)
    clean = re.sub(r"^[^\\w\\u4e00-\\u9fffA-Za-z]+", "", clean).strip()
    m = re.match(r"^([\u4e00-\u9fa5A-Za-z0-9（）()·\-\s]{4,40}?)(关于|在|于|拟|招聘|公告)", clean)
    if m:
        return re.sub(r"^[^\\w\\u4e00-\\u9fffA-Za-z]+", "", m.group(1).strip())
    return "待人工确认"


def suggestion_for_signal(signal: str, source_type: str) -> str:
    if source_type == "cninfo":
        if "设立子公司" in signal or "对外投资" in signal:
            return "优先触达董秘/证券事务代表，核实落地时间、投资节奏与合作诉求。"
        if "建设项目" in signal or "产能扩张" in signal:
            return "联系工程/供应链负责人，切入园区配套、建设周期与成本优化议题。"
        return "建立周跟踪，观察后续公告与子公司设立进展。"
    if source_type == "hkex":
        if "未來計劃" in signal:
            return "优先联系IPO项目团队或IR，围绕募资用途对接落地资源。"
        return "持续跟踪后续聆讯后资料集，确认东南亚项目是否进入执行阶段。"
    return "先做人审去噪，再联系HRBP/海外业务负责人确认岗位是否对应建厂动作。"


def build_rows(cninfo: Optional[List[Dict]], hkex: Optional[List[Dict]], brave: Optional[Dict], max_brave: int) -> List[Dict]:
    rows: List[Dict] = []

    for r in (cninfo or []):
        company = r.get("secName") or infer_company_from_title(r.get("title", ""))
        regions = "、".join(r.get("matchedRegions") or [])
        signals = "、".join(r.get("matchedSignals") or [])
        trend = r.get("title", "")
        reason = f"命中地区词[{regions}] + 信号词[{signals}]，且为交易所正式公告。"
        rows.append(
            {
                "company": company,
                "trend": trend,
                "source": f"巨潮公告: {r.get('detailUrl','')}",
                "reason": reason,
                "advice": suggestion_for_signal(signals, "cninfo"),
                "priority": "高",
                "source_type": "cninfo",
            }
        )

    for r in (hkex or []):
        hits = r.get("hits") or []
        kws = sorted({h.get("kw", "") for h in hits if isinstance(h, dict)})
        chs = sorted({h.get("chapter", "") for h in hits if isinstance(h, dict)})
        signal = "、".join([c for c in chs if c])
        trend = f"港交所申请版本命中东南亚关键词：{'、'.join([k for k in kws if k])}"
        reason = f"命中章节[{signal}]，属于上市申请文件中的披露内容。"
        rows.append(
            {
                "company": r.get("company", "待人工确认"),
                "trend": trend,
                "source": f"HKEX: {r.get('url','')}",
                "reason": reason,
                "advice": suggestion_for_signal(signal, "hkex"),
                "priority": "高",
                "source_type": "hkex",
            }
        )

    brave_rows: List[Dict] = []
    if isinstance(brave, dict):
        for group_name in ("recruitment", "tender"):
            group = brave.get(group_name) or {}
            for item in (group.get("unique_results") or [])[:max_brave]:
                if not isinstance(item, dict):
                    continue
                title = item.get("title", "")
                company = infer_company_from_title(title)
                trend = title or (item.get("description") or "")
                reason = "搜索结果出现东南亚+建厂/招聘/项目信号，属早期市场动作。"
                brave_rows.append(
                    {
                        "company": company,
                        "trend": trend,
                        "source": f"Brave/{group_name}: {item.get('url','')}",
                        "reason": reason,
                        "advice": suggestion_for_signal(group_name, "brave"),
                        "priority": "中",
                        "source_type": "brave",
                    }
                )

    # 去重：同公司优先保留高优先级来源
    priority_rank = {"高": 2, "中": 1, "低": 0}
    merged = rows + brave_rows
    best: Dict[str, Dict] = {}
    for r in merged:
        key = (r.get("company") or "").strip() + "|" + (r.get("source_type") or "")
        if key not in best or priority_rank.get(r.get("priority", "低"), 0) > priority_rank.get(best[key].get("priority", "低"), 0):
            best[key] = r

    final_rows = list(best.values())
    final_rows.sort(key=lambda x: priority_rank.get(x.get("priority", "低"), 0), reverse=True)
    return final_rows


def build_markdown(rows: List[Dict], run_date: str, stats: Dict[str, int]) -> str:
    lines = []
    lines.append(f"# 海外投资线索日报（{run_date}）")
    lines.append("")
    lines.append("## 概览")
    lines.append(f"- 高优先级线索：{stats.get('high', 0)}")
    lines.append(f"- 中优先级线索：{stats.get('mid', 0)}")
    lines.append(f"- 总线索数：{len(rows)}")
    lines.append("")
    lines.append("## 企业线索表")
    lines.append("")
    lines.append("| 公司名称 | 海外投资动向 | 信息来源 | 筛选理由 | 后续跟进建议 | 优先级 |")
    lines.append("|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(r.get("company", "")),
                    md_escape(r.get("trend", "")),
                    md_escape(r.get("source", "")),
                    md_escape(r.get("reason", "")),
                    md_escape(r.get("advice", "")),
                    md_escape(r.get("priority", "")),
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append("## 使用说明")
    lines.append("- 高优先级：交易所公告或港交所申请文件已出现明确动作。")
    lines.append("- 中优先级：搜索层早期信号，建议先人工核验后触达。")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate markdown report from workflow outputs")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1] / "output")
    parser.add_argument("--date", default=today_str())
    parser.add_argument("--max-brave", type=int, default=12)
    args = parser.parse_args()

    brave = load_json(args.output_dir / f"brave_signals_{args.date}.json")
    cninfo = load_json(args.output_dir / f"cninfo_results_{args.date}.json")
    hkex = load_json(args.output_dir / f"hkex_results_{args.date}.json")

    rows = build_rows(cninfo=cninfo, hkex=hkex, brave=brave, max_brave=args.max_brave)
    stats = {
        "high": sum(1 for r in rows if r.get("priority") == "高"),
        "mid": sum(1 for r in rows if r.get("priority") == "中"),
    }

    md = build_markdown(rows=rows, run_date=args.date, stats=stats)
    out = args.output_dir / f"lead_report_{args.date}.md"
    out.write_text(md, encoding="utf-8")

    print(f"rows: {len(rows)}")
    print(f"output: {out}")


if __name__ == "__main__":
    main()
