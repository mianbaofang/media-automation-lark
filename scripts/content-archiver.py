#!/usr/bin/env python3
"""场景 A：RSS/API 内容抓取 → LLM 结构化提取 → 写入飞书多维表格。

用法：
  python3 content-archiver.py --rss-url "https://example.com/feed.xml" --dry-run
  python3 content-archiver.py --api-url "https://api.example.com/posts" --api-key-env MY_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

EXTRACT_SYSTEM = """你是一个自媒体内容结构化提取器。给定文章的标题、正文摘要与链接，提取以下字段并以 JSON 返回：
{
  "title": "标题",
  "author": "作者/来源",
  "published_at": "发布时间 ISO8601，无法识别则 null",
  "summary": "80 字以内中文摘要",
  "category": "从[科技,财经,生活,教育,娱乐,其他]选一",
  "tags": ["标签1","标签2"],
  "sentiment": "从[正面,中性,负面]选一",
  "word_count": 整数,
  "key_points": ["核心观点1","核心观点2"]
}
只输出 JSON，不要解释；字段缺失填 null，不要编造；中文保持原语言。"""


def parse_rss(feed_url: str, limit: int) -> list[dict]:
    if not common.is_safe_url(feed_url):
        raise ValueError(f"拒绝不安全 RSS URL（SSRF 防护）: {feed_url}")
    import feedparser

    parsed = feedparser.parse(feed_url)
    entries: list[dict] = []
    for e in parsed.entries:
        if len(entries) >= limit:
            break
        authors = e.get("authors") or []
        author = e.get("author", "") or (authors[0].get("name", "") if authors else "")
        entries.append(
            {
                "title": e.get("title", ""),
                "link": e.get("link", ""),
                "summary": e.get("summary", "") or e.get("description", ""),
                "author": author,
                "published": e.get("published", "") or e.get("updated", ""),
            }
        )
    return entries


def parse_api(api_url: str, headers: dict, limit: int) -> list[dict]:
    if not common.is_safe_url(api_url):
        raise ValueError(f"拒绝不安全 API URL（SSRF 防护）: {api_url}")
    import requests

    r = requests.get(api_url, headers=headers or {}, timeout=30)
    r.raise_for_status()
    data = r.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    return items[:limit]


def build_record(entry: dict, extracted: dict) -> dict:
    fields = {
        "标题": extracted.get("title") or entry.get("title", ""),
        "作者": extracted.get("author") or entry.get("author", ""),
        "发布时间": extracted.get("published_at") or entry.get("published", ""),
        "摘要": extracted.get("summary", ""),
        "分类": extracted.get("category", "其他"),
        "标签": ", ".join(extracted.get("tags") or []),
        "情感": extracted.get("sentiment", "中性"),
        "字数": extracted.get("word_count", 0),
        "核心观点": "\n".join(extracted.get("key_points") or []),
        "链接": entry.get("link", ""),
    }
    return {"fields": fields}


def main() -> None:
    p = argparse.ArgumentParser(description="场景A：内容自动存档")
    p.add_argument("--rss-url", help="RSS/Atom 源地址")
    p.add_argument("--api-url", help="平台内容 API 地址")
    p.add_argument("--api-key-env", default=None, help="调用内容 API 时的密钥环境变量名")
    p.add_argument("--config", default=None)
    p.add_argument("--table-id", default=None, help="覆盖 config 中的归档表 table_id")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true", help="不写飞书，仅生成本地备份与预览")
    p.add_argument("--yes", action="store_true", help="高风险写操作跳过确认")
    p.add_argument("--no-notify", action="store_true", help="完成后不推送飞书通知")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    common.setup_logging(args.verbose)
    config = common.load_config(args.config)
    feishu = config.get("feishu", {})
    app_token = feishu.get("app_token")
    table_id = args.table_id or feishu.get("archive_table_id") or feishu.get("table_id")
    if not args.dry_run and (not app_token or not table_id):
        sys.exit("缺少 feishu.app_token / table_id（或 --table-id）。")

    if args.rss_url:
        common.logger.info("抓取 RSS: %s", args.rss_url)
        entries = parse_rss(args.rss_url, args.limit)
    elif args.api_url:
        headers: dict = {}
        if args.api_key_env:
            headers["Authorization"] = f"Bearer {os.environ.get(args.api_key_env, '')}"
        common.logger.info("抓取 API: %s", args.api_url)
        entries = parse_api(args.api_url, headers, args.limit)
    else:
        sys.exit("请指定 --rss-url 或 --api-url。")

    common.logger.info("获取到 %d 条内容", len(entries))

    seen = common.load_seen(config)
    records: list[dict] = []
    for entry in entries:
        link = entry.get("link", "")
        if link and common.dedup_key(link) in seen:
            common.logger.info("已归档，跳过: %s", link)
            continue
        user = json.dumps(
            {
                "title": entry.get("title", ""),
                "summary": (entry.get("summary", "") or "")[:2000],
                "link": entry.get("link", ""),
            },
            ensure_ascii=False,
        )
        try:
            extracted = common.llm_chat(EXTRACT_SYSTEM, user, config, expect_json=True)
        except Exception as e:  # noqa: BLE001
            common.logger.warning("提取失败，跳过: %s | %s", entry.get("title"), e)
            extracted = {}
        # 摘要 / 核心观点经 renhua 去 AI 味（未启用或无 key 时原样保留）
        if extracted:
            extracted["summary"] = common.polish_text(extracted.get("summary", "") or "", config)
            kps = extracted.get("key_points") or []
            if kps:
                joined = common.polish_text("\n".join(kps), config)
                extracted["key_points"] = [k for k in joined.split("\n") if k.strip()]
        records.append(build_record(entry, extracted))

    out_dir = common.ensure_output_dir(config)
    backup = os.path.join(out_dir, "archiver_backup.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    common.logger.info("本地备份: %s", backup)

    res = common.write_bitable_records(app_token, table_id, records, config, dry_run=args.dry_run, yes=args.yes)
    written = res.get("data", {}).get("written", len(records)) if not args.dry_run else len(records)
    common.logger.info("飞书写入记录数: %d", written)
    if not args.dry_run:
        for r in records:
            lk = r["fields"].get("链接", "")
            if lk:
                common.mark_seen(config, lk)

    if not args.no_notify and not args.dry_run and feishu.get("chat_id"):
        common.send_im(feishu["chat_id"], f"内容归档完成：新增 {written} 条", config, as_bot=True)

    print(json.dumps({"ok": True, "written": written, "backup": backup}, ensure_ascii=False))


if __name__ == "__main__":
    main()
