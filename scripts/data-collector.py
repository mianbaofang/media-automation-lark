#!/usr/bin/env python3
"""场景 B：多平台数据抓取 → 指标计算 → 写入飞书多维表格并刷新看板（HTML 可视化）。

用法：
  python3 data-collector.py --source metrics.json --push
  python3 data-collector.py --source metrics.csv --report-yesterday --chat-id oc_xxxx
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import platforms_fetcher  # noqa: E402

INSIGHT_SYSTEM = """你是一个新媒体数据分析师。给定某平台一段时间的核心指标，输出 JSON：
{
  "best_performer": "表现最好的内容标题或 null",
  "trend": "从[上升,平稳,下降]选一",
  "insight": "一句话运营洞察",
  "recommendation": "一句可执行建议"
}
只输出 JSON，不要解释。"""


def load_source(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        if path.endswith(".csv"):
            import pandas as pd

            return pd.read_csv(path).to_dict(orient="records")
        return json.load(f)


def _col(df, *names: str):
    norm = {c.lower(): c for c in df.columns}
    for n in names:
        if n in norm:
            return norm[n]
    return None


def compute_metrics(rows: list[dict]):
    import pandas as pd

    df = pd.DataFrame(rows)
    c_reads = _col(df, "reads", "阅读", "播放")
    c_likes = _col(df, "likes", "点赞")
    c_comments = _col(df, "comments", "评论")
    c_shares = _col(df, "shares", "转发", "分享")
    c_followers = _col(df, "followers", "新增粉丝", "涨粉")
    c_platform = _col(df, "platform", "平台")

    total_reads = int(df[c_reads].sum()) if c_reads else 0
    total_likes = int(df[c_likes].sum()) if c_likes else 0
    total_comments = int(df[c_comments].sum()) if c_comments else 0
    total_shares = int(df[c_shares].sum()) if c_shares else 0
    engagement = (total_likes + total_comments + total_shares) / total_reads if total_reads else 0
    summary = {
        "total_reads": total_reads,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "engagement_rate": round(engagement, 4),
        "days": int(len(df)),
        "platforms": sorted(set(df[c_platform].tolist())) if c_platform else [],
    }
    return summary, df


def render_dashboard(summary: dict, df, out_path: str) -> str:
    norm = {c.lower(): c for c in df.columns}
    date_col = next((norm[k] for k in ("date", "日期") if k in norm), None)
    read_col = next((norm[k] for k in ("reads", "阅读", "播放") if k in norm), None)
    bars = ""
    if date_col and read_col:
        daily = df.groupby(df[date_col].astype(str))[read_col].sum().sort_index()
        maxv = int(daily.max()) if len(daily) else 0
        for d, v in daily.items():
            h = int(200 * v / maxv) if maxv else 0
            bars += f'<div class="bar" style="height:{h}px" title="{d}: {int(v)}"></div>\n'
    else:
        bars = '<p>未检测到日期/阅读列，无法绘制趋势图。</p>'

    cards = "".join(
        f'<div class="card"><b>{summary[k]}</b><br>{label}</div>'
        for k, label in [
            ("total_reads", "总阅读/播放"),
            ("total_likes", "总点赞"),
            ("total_comments", "总评论"),
            ("total_shares", "总转发"),
        ]
    )
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>运营看板</title>
<style>
body{{font-family:system-ui,'PingFang SC',sans-serif;margin:2rem;color:#1f2329}}
h1{{font-size:1.4rem}} .kpi{{display:flex;gap:1rem;flex-wrap:wrap}}
.card{{border:1px solid #dee0e3;border-radius:8px;padding:1rem;min-width:120px}}
.chart{{display:flex;align-items:flex-end;gap:6px;height:220px;margin-top:1rem;border-bottom:1px solid #dee0e3}}
.bar{{flex:1;background:#3370ff;border-radius:4px 4px 0 0;min-width:6px}}
.rate{{margin-top:1rem;font-size:1.1rem}}
</style></head>
<body>
<h1>自媒体运营看板</h1>
<div class="kpi">{cards}</div>
<div class="rate">互动率：<b>{summary['engagement_rate'] * 100:.2f}%</b> ｜ 统计天数：{summary['days']} ｜ 平台：{', '.join(summary['platforms']) or '—'}</div>
<h2>每日阅读趋势</h2>
<div class="chart">{bars}</div>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main() -> None:
    p = argparse.ArgumentParser(description="场景B：数据搜集与可视化")
    p.add_argument("--source", default=None, help="JSON/CSV 指标文件（与 --fetch 二选一或并用）")
    p.add_argument("--fetch", action="store_true", help="按 config.platforms 自动抓取平台指标")
    p.add_argument("--config")
    p.add_argument("--platform", default=None)
    p.add_argument("--push", action="store_true", help="写入飞书多维表格")
    p.add_argument("--report-yesterday", action="store_true", help="仅统计昨日并推送通知")
    p.add_argument("--chat-id", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--no-notify", action="store_true", help="完成后不推送飞书通知")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    common.setup_logging(args.verbose)
    config = common.load_config(args.config)
    feishu = config.get("feishu", {})

    rows: list[dict] = []
    if args.fetch:
        only = [args.platform] if args.platform else None
        rows += platforms_fetcher.fetch_all(config, only=only)
    if args.source:
        rows += load_source(args.source)
    if not rows:
        sys.exit("无数据。用 --fetch 自动抓取平台，或 --source file.json/csv 喂入。")
    if args.report_yesterday:
        y = (date.today() - timedelta(days=1)).isoformat()[:10]
        rows = [r for r in rows if str(r.get("date", r.get("日期", ""))).startswith(y)]
    summary, df = compute_metrics(rows)
    common.logger.info("汇总: %s", summary)

    out_dir = common.ensure_output_dir(config)
    dash = os.path.join(out_dir, "dashboard.html")
    render_dashboard(summary, df, dash)
    common.logger.info("看板已生成: %s", dash)

    # 可选：导出 xlsx（需 openpyxl，pandas 依赖）
    try:
        xlsx = os.path.join(out_dir, "metrics.xlsx")
        df.to_excel(xlsx, index=False)
        common.logger.info("指标表已导出: %s", xlsx)
    except Exception as e:  # noqa: BLE001
        common.logger.debug("xlsx 导出跳过: %s", e)

    feishu_write = (args.push or args.report_yesterday) and not args.dry_run
    written = 0
    if feishu_write and feishu.get("app_token") and feishu.get("metrics_table_id"):
        seen = common.load_seen(config)

        def _dk(r):
            d = r.get("date", r.get("日期", ""))
            p = r.get("platform", r.get("平台", args.platform or ""))
            return common.dedup_key(f"{d}|{p}")

        new_rows = [r for r in rows if _dk(r) not in seen]
        records = [
            {
                "fields": {
                    "日期": r.get("date", r.get("日期", "")),
                    "平台": r.get("platform", r.get("平台", args.platform or "")),
                    "阅读": r.get("reads", r.get("阅读", r.get("播放", 0))),
                    "点赞": r.get("likes", r.get("点赞", 0)),
                    "评论": r.get("comments", r.get("评论", 0)),
                    "转发": r.get("shares", r.get("转发", r.get("分享", 0))),
                    "新增粉丝": r.get("followers", r.get("新增粉丝", r.get("涨粉", 0))),
                }
            }
            for r in new_rows
        ]
        if records:
            res = common.write_bitable_records(
                feishu["app_token"], feishu["metrics_table_id"], records, config, dry_run=args.dry_run, yes=args.yes
            )
            written = res.get("data", {}).get("written", len(records))
            for r in new_rows:
                common.mark_seen(config, _dk(r))
        else:
            common.logger.info("无新记录（全部已归档）。")
    else:
        common.logger.info("未写入飞书（需 --push 且配置 metrics_table_id，或 --report-yesterday）。")

    insight: dict = {}
    try:
        insight = common.llm_chat(INSIGHT_SYSTEM, json.dumps(summary, ensure_ascii=False), config, expect_json=True)
    except Exception as e:  # noqa: BLE001
        common.logger.warning("洞察生成失败: %s", e)

    msg = (
        f"数据看板更新：总阅读 {summary['total_reads']}，互动率 {summary['engagement_rate'] * 100:.2f}%。"
        + (f" 洞察：{insight.get('insight', '')}" if insight else "")
    )
    chat = args.chat_id or feishu.get("chat_id")
    if chat and (args.report_yesterday or args.push) and not args.dry_run and not args.no_notify:
        common.send_im(chat, msg, config, as_bot=True)

    print(
        json.dumps(
            {"ok": True, "summary": summary, "written": written, "dashboard": dash, "insight": insight},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
