# Openclaw 抓取工作流迁移版

这个目录把你在 Openclaw 里的 LeadScreener 抓取流程迁移为本地可运行脚本，保留了核心 API 与执行顺序。

## 已迁移内容

1. `scripts/cninfo_announcements.py`
- 对应 Openclaw 的巨潮资讯接口流程
- API: `POST http://www.cninfo.com.cn/new/hisAnnouncement/query`
- 先访问首页拿 session cookie，再发 POST
- 支持地区词/信号词/排除词与时间窗口
- 支持自动翻页抓取（`--max-pages`）

2. `scripts/hkex_screener.py`
- 对应 Openclaw 的港交所两阶段扫描
- 默认从 HKEX 官方 JSON 索引动态发现“主板-处理中-申请版本”URL
- 动态源失败时自动回退到 `seed_hkex_urls.txt`
- 阶段一：`概要/業務概要` 预筛
- 阶段二：`風險因素` + `未來計劃` 精读
- 可用 `--max-companies` 控制扫描规模

3. `scripts/run_workflow.py`
- 串联执行 Brave + cninfo + hkex
- 默认最后自动生成 Markdown 报告（可读）

4. `scripts/brave_search_signals.py`
- 对接 Brave Search Web API（真实调用）
- 覆盖“招聘层 + 招投标层”预置 query
- 输出去重后的线索结果

5. `scripts/generate_markdown_report.py`
- 汇总 Brave / 巨潮 / HKEX 输出，生成可读 Markdown 报告
- 企业信息表格字段：公司名称、海外投资动向、信息来源、筛选理由、后续跟进建议、优先级

## 与原 Openclaw 版本相比的修复

1. 修复原 `hkex_screener.py` 输出路径 bug（原脚本把 `$(date ...)` 当普通字符串且 `~` 不会自动展开）。
2. 去掉硬编码 site-packages 路径，改为标准依赖安装。
3. 输出统一写入 `output/`，便于后处理。
4. Firecrawl 分支已移除，当前仅保留 Brave 配置入口。

## 使用方法

```bash
cd workflows/openclaw-migrated
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/run_workflow.py
```

只跑 Brave（招聘/招投标）：

```bash
python scripts/run_workflow.py --skip-cninfo --skip-hkex
```

仅跑巨潮：

```bash
python scripts/run_workflow.py --skip-hkex --start-date 2026-02-01 --end-date 2026-03-08
```

控制抓取规模（推荐）：

```bash
python scripts/run_workflow.py --cninfo-max-pages 5 --hkex-max-companies 80
```

跳过 Markdown 报告生成：

```bash
python scripts/run_workflow.py --skip-report
```

仅跑港交所：

```bash
python scripts/run_workflow.py --skip-cninfo
```

## 输出文件

- `output/brave_signals_YYYYMMDD.json`
- `output/cninfo_results_YYYYMMDD.json`
- `output/hkex_results_YYYYMMDD.json`
- `output/lead_report_YYYYMMDD.md`
