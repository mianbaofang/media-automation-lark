#!/usr/bin/env python3
"""场景 D：智能搜索采集 → 分类 Markdown。

按用户的查询词，调用当前可用的搜索后端（anysearch / tavily …）收集候选文章，
再用可用的抓取后端（autocli / anysearch / tavily / http 兜底）取正文，
按分类规则存成带 frontmatter 的 Markdown 文件，目录自动归类；可选归档到飞书。

设计要点（对应"运行时检测、没装不废"）：
- 自动检测后端；缺失的后端跳过，绝不让流程崩溃。
- 没有任何可用搜索后端且也没给 RSS 时，给出明确的安装命令后退出（不静默失败）。
- 所有脆弱操作（飞书写入、LLM、HTTP）走 common.py，重试集中管理。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import search_backends as sb


def _log(*a):
    sys.stderr.write(" ".join(str(x) for x in a) + "\n")


def parse_category_map(text: str) -> list[tuple[str, list[str]]]:
    """ 'AI:大模型,LLM;产品:增长,PM' -> [('AI',['大模型','LLM']), ('产品',['增长','PM'])] """
    out = []
    if not text:
        return out
    for part in text.split(";"):
        part = part.strip()
        if not part or ":" not in part:
            continue
        cat, kws = part.split(":", 1)
        out.append((cat.strip(), [k.strip() for k in kws.split(",") if k.strip()]))
    return out


def classify(title: str, url: str, query: str, cat_map: list[tuple[str, list[str]]], default: str) -> str:
    blob = f"{title} {url} {query}".lower()
    for cat, kws in cat_map:
        for kw in kws:
            if kw.lower() in blob:
                return cat
    return default


def safe_name(s: str, maxlen: int = 60) -> str:
    s = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", s).strip().strip("._")
    s = re.sub(r"\s+", "_", s)
    return s[:maxlen] or "untitled"


def write_markdown(out_dir: str, category: str, title: str, url: str, md: str,
                   query: str, backend: str, tags: list[str]) -> str:
    cat_dir = os.path.join(out_dir, safe_name(category))
    os.makedirs(cat_dir, exist_ok=True)
    date = dt.date.today().isoformat()
    fname = f"{date}-{safe_name(title)}.md"
    path = os.path.join(cat_dir, fname)
    front = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f'source: "{url}"',
        f'date: {date}',
        f'category: "{category}"',
        f'query: "{query.replace(chr(34), chr(39))}"',
        f'backend: "{backend}"',
        f'tags: [{", ".join(tags)}]',
        "---",
        "",
        f"# {title}",
        "",
        f"> 来源: [{url}]({url})  ·  检索词: {query}  ·  后端: {backend}",
        "",
        md.strip(),
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(front))
    return path


def build_index(out_dir: str, rows: list[dict], intro: str = "") -> str:
    lines = ["# 采集索引", "", f"生成时间: {dt.datetime.now().isoformat(timespec='seconds')}", f"条目数: {len(rows)}", ""]
    if intro:
        lines.append(intro)
        lines.append("")
    cats: dict[str, list[dict]] = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    for cat, items in cats.items():
        lines.append(f"## {cat}")
        for it in items:
            lines.append(f"- [{it['title']}]({safe_name(cat)}/{os.path.basename(it['path'])}) — {it['url']}")
        lines.append("")
    path = os.path.join(out_dir, "index.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


OFFLINE_SAMPLES = [
    {
        "query": "LLM 应用落地",
        "results": [
            {"title": "如何用 LLM 重构客服工作流", "url": "https://example.com/llm-support",
             "snippet": "介绍用大模型替代人工客服的实践", "backend": "anysearch"},
            {"title": "Agent 在自媒体运营中的用法", "url": "https://example.com/agent-media",
             "snippet": "自动化选题与分发", "backend": "anysearch"},
        ],
        "markdown": {
            "https://example.com/llm-support": "# 如何用 LLM 重构客服工作流\n\n正文示例：通过检索增强降低幻觉……",
            "https://example.com/agent-media": "# Agent 在自媒体运营中的用法\n\n正文示例：自动采集、分类、定时发布。",
        },
    }
]


def main():
    p = argparse.ArgumentParser(description="智能搜索采集 → 分类 Markdown")
    p.add_argument("--config", default=None)
    p.add_argument("--query", action="append", default=None, help="检索词，可重复")
    p.add_argument("--category-map", default=None, help="分类映射，如 'AI:大模型,LLM;产品:增长'")
    p.add_argument("--backends", default=None, help="限定后端，逗号分隔，如 anysearch,tavily")
    p.add_argument("--rss-url", action="append", default=None, help="附加 RSS 源（可选）")
    p.add_argument("--max-per-query", type=int, default=5)
    p.add_argument("--default-category", default="综合")
    p.add_argument("--no-fetch", action="store_true", help="只列 URL，不抓正文")
    p.add_argument("--no-archive", action="store_true", help="不归档到飞书")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--offline-demo", action="store_true", help="用内置样例跑通写盘/分类（不联网）")
    p.add_argument("--output-dir", default=None)
    p.add_argument("--no-notify", action="store_true")
    p.add_argument("--no-polish", action="store_true", help="关闭 renhua 去 AI 味润色（默认开启）")
    p.add_argument("--polish-body", action="store_true", help="连抓取的正文也用 renhua 润色（默认只润色本 skill 生成的文字）")
    p.add_argument("--verbose", "-v", action="store_true")
    a = p.parse_args()

    common.setup_logging(a.verbose)
    # config 仅用于飞书归档；采集本身不依赖它，缺失则用空配置继续
    try:
        config = common.load_config(a.config)
    except FileNotFoundError:
        config = {}
    # 命令行开关覆盖 config 的 text 段
    config.setdefault("text", {})
    if a.no_polish:
        config["text"]["polish"] = False
    if a.polish_body:
        config["text"]["polish_body"] = True

    # 合并配置：命令行优先，其次 config.json 的 search 段
    scfg = config.get("search", {}) if isinstance(config, dict) else {}
    queries = a.query or scfg.get("queries") or []
    cat_map = parse_category_map(a.category_map or scfg.get("category_map") or "")
    default_cat = a.default_category or scfg.get("default_category") or "综合"
    rss_urls = a.rss_url or scfg.get("rss_urls") or []
    only = [b.strip() for b in (a.backends or scfg.get("backends") or "").split(",") if b.strip()] or None
    out_dir = a.output_dir or (config.get("paths", {}) or {}).get("output_dir") or os.path.join(os.getcwd(), "output")
    os.makedirs(out_dir, exist_ok=True)

    # 1) 运行时检测后端
    status = sb.detect()
    _log("【后端检测】")
    for name, s in status.items():
        flag = "✓" if (s["installed"] and s["working"]) else ("○" if s["installed"] else "✗")
        _log(f"  {flag} {name:12s} {s['label']}  — {s['note']}")

    usable_search = sb.usable_search_backends(only)
    if not a.offline_demo and not usable_search and not rss_urls:
        _log("\n⚠️ 没有任何可用的搜索后端，也没有提供 RSS 源，无法采集。")
        _log("   安装搜索后端（已装的会自动跳过）：")
        _log("     python scripts/install_backends.py --all")
        _log("   或从 GitHub 手动拉取后，再运行本脚本。")
        sys.exit(2)

    rows: list[dict] = []

    # 2) 离线演示：用内置样例走通分类/写盘
    if a.offline_demo:
        for sample in OFFLINE_SAMPLES:
            for item in sample["results"]:
                cat = classify(item["title"], item["url"], sample["query"], cat_map, default_cat)
                md = sample["markdown"].get(item["url"], item["snippet"])
                if config["text"].get("polish_body"):
                    md = common.polish_text(md, config, max_chars=20000)
                path = write_markdown(out_dir, cat, item["title"], item["url"], md,
                                      sample["query"], item["backend"], [cat])
                rows.append({"title": item["title"], "url": item["url"], "category": cat, "query": sample["query"], "path": path})
        intro = common.polish_text(f"本次共采集 {len(rows)} 篇内容，覆盖 {len(set(r['category'] for r in rows))} 个分类。", config) if rows else ""
        idx = build_index(out_dir, rows, intro)
        _log(f"\n[OFFLINE-DEMO] 已写入 {len(rows)} 篇示例到 {out_dir}")
        _log(f"  索引: {idx}")
        return

    # 3) 真实采集
    import feedparser  # 延迟导入
    seen = set()
    for q in queries:
        _log(f"\n【检索】{q}")
        results = sb.search_all(q, n=a.max_per_query, only=only)
        for it in results:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            _log(f"  - {it['title']}  ({it['backend']})")
            md = ""
            if not a.no_fetch:
                md = sb.fetch_markdown(it["url"], only) or ""
            if config["text"].get("polish_body") and md:
                md = common.polish_text(md, config, max_chars=20000)
            cat = classify(it["title"], it["url"], q, cat_map, default_cat)
            path = write_markdown(out_dir, cat, it["title"], it["url"],
                                  md or it["snippet"], q, it["backend"], [cat])
            rows.append({"title": it["title"], "url": it["url"], "category": cat, "path": path})

    for u in rss_urls:
        _log(f"\n【RSS】{u}")
        if u.lower().startswith(("http://", "https://")) and not common.is_safe_url(u):
            _log(f"  跳过不安全 URL（SSRF 防护）: {u}")
            continue
        try:
            parsed = feedparser.parse(u)
            for e in parsed.entries[: a.max_per_query]:
                link = getattr(e, "link", "")
                if not link or link in seen:
                    continue
                seen.add(link)
                title = getattr(e, "title", link)
                md = sb.fetch_markdown(link, only) or getattr(e, "summary", "")
                cat = classify(title, link, u, cat_map, default_cat)
                path = write_markdown(out_dir, cat, title, link, md, u, "rss", [cat])
                rows.append({"title": title, "url": link, "category": cat, "query": u, "path": path})
        except Exception as ex:
            _log(f"  RSS 解析失败: {ex}")

    intro = common.polish_text(f"本次共采集 {len(rows)} 篇内容，覆盖 {len(set(r['category'] for r in rows))} 个分类。", config) if rows else ""
    idx = build_index(out_dir, rows, intro)
    _log(f"\n【完成】共 {len(rows)} 篇，已写入 {out_dir}")
    _log(f"  索引: {idx}")

    # 4) 可选归档到飞书
    feishu = config.get("feishu", {})
    if not a.no_archive and rows:
        app_token = feishu.get("app_token") or os.environ.get("FEISHU_APP_TOKEN")
        table_id = feishu.get("archive_table_id") or os.environ.get("FEISHU_ARCHIVE_TABLE_ID")
        if app_token and table_id:
            seen = common.load_seen(config)
            new_rows = [r for r in rows if common.dedup_key(r["url"]) not in seen]
            skipped = len(rows) - len(new_rows)
            if skipped:
                _log(f"  去重跳过 {skipped} 条已归档")
            records = [{"fields": {
                "标题": r["title"], "链接": r["url"], "分类": r["category"],
                "检索词": r["query"] if "query" in r else "", "路径": r["path"],
                "采集时间": dt.datetime.now().isoformat(timespec="seconds"),
            }} for r in new_rows]
            if records:
                res = common.write_bitable_records(app_token, table_id, records, config, dry_run=a.dry_run, yes=True)
                if not a.dry_run:
                    for r in new_rows:
                        common.mark_seen(config, r["url"])
                _log(f"  飞书归档: {res.get('data', {}).get('written', 0)} 条（dry_run={a.dry_run}）")
            else:
                _log("  无新记录可写（全部已归档）")
        else:
            _log("  未配置飞书 app_token/table_id，跳过归档。")

    # 5) 可选机器人通知
    if not a.no_notify and not a.dry_run:
        chat = feishu.get("chat_id") or os.environ.get("FEISHU_CHAT_ID")
        if chat:
            common.send_im(chat, f"采集完成：{len(rows)} 篇，索引 {idx}", config, dry_run=a.dry_run)

    print(json.dumps({"ok": True, "count": len(rows), "index": idx, "output_dir": out_dir}, ensure_ascii=False))


if __name__ == "__main__":
    main()
