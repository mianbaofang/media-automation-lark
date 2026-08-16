#!/usr/bin/env python3
"""平台指标抓取适配器（场景 B 的"自动抓取"部分）。

设计：
- 注册表 REGISTRY：平台名 -> fetcher(cfg) -> list[dict]，每行归一化为
  {date, platform, reads, likes, comments, shares, followers}。
- 未实现的平台抛 NotImplementedError，上层捕获后提示用 --source 文件喂入。
- 网络失败不阻断整个流程，只 warning 该平台并继续其它。

当前已实现：bilibili（公开接口，免 key，可能受站点反爬影响，失败会降级）。
扩展新平台：在此文件加一个 fetch_xxx(cfg) 并注册到 REGISTRY。
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("media-automation")

REGISTRY: dict = {}


def fetch_bilibili(cfg: dict) -> list[dict]:
    """拉取用户最近投稿的播放/互动指标。需 config.platforms.bilibili.mid。"""
    import requests

    mid = str(cfg.get("mid") or "").strip()
    if not mid:
        raise ValueError("bilibili 需在 config.platforms.bilibili.mid 配置用户 UID")
    url = f"https://api.bilibili.com/x/space/arc/search?mid={mid}&pn=1&ps=30&order=pubdate"
    r = requests.get(
        url, timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (compatible; media-automation/1.0)",
                 "Referer": f"https://space.bilibili.com/{mid}"},
    )
    data = r.json()
    if data.get("code") != 0:
        raise RuntimeError(f"bilibili 接口返回 code={data.get('code')} msg={data.get('message')}")
    vlist = data.get("data", {}).get("list", {}).get("vlist", []) or []
    rows: list[dict] = []
    for v in vlist:
        ts = v.get("created")
        d = datetime.fromtimestamp(int(ts)).date().isoformat() if ts else ""
        rows.append({
            "date": d, "platform": "bilibili",
            "reads": v.get("play", 0),
            "likes": v.get("video_review", 0),
            "comments": v.get("comment", 0),
            "shares": v.get("favorites", 0),
            "followers": 0,
        })
    return rows


REGISTRY["bilibili"] = fetch_bilibili


def fetch_all(config: dict, only: list[str] | None = None) -> list[dict]:
    """遍历 config.platforms，调用已实现的适配器抓取；失败的平台跳过不阻断。"""
    platforms = config.get("platforms", {}) or {}
    rows: list[dict] = []
    for name, cfg in platforms.items():
        if only and name not in only:
            continue
        fn = REGISTRY.get(name)
        if not fn:
            logger.warning("平台 %s 未实现自动抓取，请用 --source 文件喂入其指标", name)
            continue
        try:
            got = fn(cfg or {})
            rows.extend(got)
            logger.info("平台 %s 抓取到 %d 条", name, len(got))
        except Exception as e:  # noqa: BLE001
            logger.warning("平台 %s 抓取失败：%s（可用 --source 喂入文件）", name, e)
    return rows


if __name__ == "__main__":
    import json
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import common
    cfg = common.load_config(None if len(sys.argv) < 2 else sys.argv[1])
    print(json.dumps(fetch_all(cfg), ensure_ascii=False, indent=2))
