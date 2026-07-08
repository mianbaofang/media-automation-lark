#!/usr/bin/env python3
"""Local web control panel for Media Automation Lark.

The panel is intentionally dependency-free. Agent runtimes should open it via
``scripts/panel-agent.py`` so end users do not need to type shell commands.
Feishu writes stay opt-in.
"""
from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PANEL_DIR = ROOT / "output_panel"
PANEL_OUTPUT = PANEL_DIR / "output"
PANEL_CONFIG = PANEL_DIR / "gui-config.json"
DEFAULT_CATEGORY = "AI:大模型,LLM,Agent;产品:增长,运营;技术:Python,自动化"
CATEGORY_PRESETS = {
    "default": DEFAULT_CATEGORY,
    "platform": "微信:微信,公众号,mp.weixin.qq.com;B站:B站,bilibili;小红书:小红书,xiaohongshu;抖音:抖音,douyin",
    "content_ops": "选题:热点,趋势,爆款,选题;案例:案例,复盘,拆解;工具:工具,教程,方法;数据:数据,指标,报告",
    "none": "",
}
CATEGORY_OPTIONS = [
    ("default", "默认：AI / 产品 / 技术"),
    ("platform", "平台：微信 / B站 / 小红书 / 抖音"),
    ("content_ops", "内容：选题 / 案例 / 工具 / 数据"),
    ("none", "不分组：放进综合"),
    ("custom", "自定义…"),
]
SOURCE_SCOPES = [
    ("public_web", "全网公开网页"),
    ("wechat_public", "微信公众号公开页"),
    ("bilibili", "B 站公开页"),
    ("zhihu", "知乎公开页"),
    ("xiaohongshu", "小红书公开页"),
    ("douyin", "抖音公开页"),
    ("custom", "我自己指定网站 / 账号"),
]
RANK_MODES = [
    ("hotness", "优先看爆款迹象"),
    ("relevance", "优先看最相关"),
    ("category", "优先看分类匹配"),
    ("author", "优先看指定作者 / 账号"),
]
ACTION_TITLES = {
    "env": "环境检查",
    "offline": "先体验一次完整流程",
    "material": "直接丢网页或文件",
    "search": "按选题去采集",
    "rss": "订阅源自动归档",
    "dashboard": "看板和定时",
}
ACTION_TIMEOUTS = {
    "env": 60,
    "offline": 60,
    "material": 45,
    "search": 45,
    "rss": 45,
    "dashboard": 45,
}


def ensure_panel_config() -> Path:
    PANEL_OUTPUT.mkdir(parents=True, exist_ok=True)
    if not PANEL_CONFIG.exists():
        cfg = {
            "feishu": {
                "app_token": "",
                "archive_table_id": "",
                "metrics_table_id": "",
                "materials_table_id": "",
                "chat_id": "",
                "lark_cli_path": "lark-cli",
                "data_flag": "--data",
            },
            "llm": {"env_key": "LARK_LLM_API_KEY", "api_key": "@env:LARK_LLM_API_KEY"},
            "paths": {"output_dir": str(PANEL_OUTPUT)},
            "text": {"polish": False, "polish_body": False},
        }
        PANEL_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return PANEL_CONFIG


def project_config() -> Path:
    cfg = ROOT / "config.json"
    return cfg if cfg.exists() else ensure_panel_config()


def field(form: dict[str, list[str]], name: str, default: str = "") -> str:
    return (form.get(name, [default])[0] or default).strip()


def checked(form: dict[str, list[str]], name: str) -> bool:
    return field(form, name).lower() in {"1", "true", "on", "yes"}


def safe_int(value: str, default: int, lo: int, hi: int) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, num))


def split_items(text: str) -> list[str]:
    items: list[str] = []
    for raw in text.replace("；", "\n").replace(";", "\n").splitlines():
        item = raw.strip().strip("-*•、,， ")
        if item:
            items.append(item)
    return items


def option_tags(options: list[tuple[str, str]], selected: str = "") -> str:
    tags = []
    for value, label in options:
        sel = " selected" if value == selected else ""
        tags.append(f'<option value="{html.escape(value)}"{sel}>{html.escape(label)}</option>')
    return "".join(tags)


def category_map_from_form(form: dict[str, list[str]]) -> str:
    raw = field(form, "category_map")
    if raw:
        return raw
    preset = field(form, "category_preset", "default")
    if preset == "custom":
        return field(form, "custom_category_map", DEFAULT_CATEGORY)
    return CATEGORY_PRESETS.get(preset, DEFAULT_CATEGORY)


def rel_script(name: str) -> str:
    return str(SCRIPTS / name)


def sample_metrics_path() -> Path:
    PANEL_DIR.mkdir(parents=True, exist_ok=True)
    path = PANEL_DIR / "sample_metrics.json"
    if not path.exists():
        rows = [
            {"date": "2026-07-01", "platform": "bilibili", "reads": 2300, "likes": 180, "comments": 32, "shares": 21},
            {"date": "2026-07-02", "platform": "bilibili", "reads": 3100, "likes": 240, "comments": 44, "shares": 36},
            {"date": "2026-07-03", "platform": "wechat", "reads": 1800, "likes": 95, "comments": 18, "shares": 12},
        ]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def action_title(action: str) -> str:
    return ACTION_TITLES.get(action, action)


def config_arg(form: dict[str, list[str]]) -> Path:
    raw = field(form, "config")
    if raw:
        return Path(raw)
    return project_config()


def build_command(action: str, form: dict[str, list[str]]) -> tuple[list[str], str]:
    py = sys.executable
    cfg = config_arg(form)

    if action == "env":
        return [py, rel_script("env-check.py")], action_title(action)

    if action == "offline":
        out = PANEL_OUTPUT / "offline-demo"
        return [
            py,
            rel_script("collector.py"),
            "--config",
            str(cfg),
            "--offline-demo",
            "--category-map",
            category_map_from_form(form),
            "--output-dir",
            str(out),
            "--no-archive",
            "--no-notify",
            "--no-polish",
        ], action_title(action)

    if action == "dashboard":
        source = field(form, "source") or str(sample_metrics_path())
        cmd = [py, rel_script("data-collector.py"), "--config", str(cfg), "--source", source]
        if checked(form, "write_feishu"):
            cmd += ["--push", "--yes"]
        else:
            cmd.append("--dry-run")
        return cmd, action_title(action)

    if action == "rss":
        rss = field(form, "rss_url")
        if not rss:
            raise ValueError("请填写 RSS 地址。")
        cmd = [
            py,
            rel_script("content-archiver.py"),
            "--config",
            str(cfg),
            "--rss-url",
            rss,
            "--limit",
            str(safe_int(field(form, "limit"), 10, 1, 100)),
        ]
        if checked(form, "write_feishu"):
            cmd += ["--yes"]
        else:
            cmd += ["--dry-run", "--no-notify"]
        return cmd, action_title(action)

    if action == "search":
        queries = split_items(field(form, "query"))
        if not queries:
            raise ValueError("请先写下要采集的选题清单，每行一个主题。")
        out = PANEL_OUTPUT / "search"
        cmd = [
            py,
            rel_script("collector.py"),
            "--config",
            str(cfg),
            "--category-map",
            category_map_from_form(form),
            "--max-per-query",
            str(safe_int(field(form, "max_per_query"), 5, 1, 20)),
            "--source-scope",
            field(form, "source_scope", "public_web"),
            "--rank-by",
            field(form, "rank_by", "hotness"),
            "--output-dir",
            str(out),
            "--no-fetch",
            "--no-polish",
        ]
        for query in queries:
            cmd += ["--query", query]
        source_filter = field(form, "source_filter")
        if source_filter:
            cmd += ["--source-filter", source_filter]
        author_filter = field(form, "author_filter")
        if author_filter:
            cmd += ["--author-filter", author_filter]
        if checked(form, "write_feishu"):
            cmd += ["--yes"]
        else:
            cmd += ["--dry-run", "--no-archive", "--no-notify"]
        return cmd, action_title(action)

    if action == "material":
        typ = field(form, "material_type", "text")
        value = field(form, "material_value")
        if not value:
            raise ValueError("请填写素材内容、URL 或文件路径。")
        flag = {"url": "--url", "file": "--file", "text": "--text"}.get(typ, "--text")
        cmd = [py, rel_script("material-manager.py"), "--config", str(cfg), flag, value]
        if checked(form, "write_feishu"):
            cmd += ["--yes"]
        else:
            cmd += ["--dry-run", "--no-notify"]
        return cmd, action_title(action)

    raise ValueError(f"未知操作：{action}")


def run_action(action: str, form: dict[str, list[str]]) -> dict[str, object]:
    cmd, title = build_command(action, form)
    timeout = ACTION_TIMEOUTS.get(action, 60)
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return {
            "action": action,
            "title": title,
            "cmd": cmd,
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": f"运行时间超过 {timeout} 秒，已停止。这通常是外部网站、搜索后端或模型服务响应太慢。",
        }
    return {"action": action, "title": title, "cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def next_steps(action: str, ok: bool) -> str:
    if not ok:
        if action == "env":
            return "<p>环境还没完全准备好。你不用自己输入命令，把下面“检查结果”里缺的部分交给 Agent 处理即可。</p>"
        return "<p>这一步没有跑通。先看“检查结果”里的提示；如果需要排查，再展开下面的详细记录给 Agent 看。</p>"
    if action == "offline":
        return """
<p>这是一次安全试玩：系统用内置样例文章跑了一遍整理流程，没有联网，也没有写入飞书。</p>
<p>下一步可以在左侧状态栏打开“样例结果”，看它整理出来的目录和文章结构。确认这种结果符合预期后，再回到面板处理真实网页、文件或搜索主题。</p>
"""
    if action == "material":
        return "<p>素材已处理完成。你可以先看输出内容是否可用；确认没问题后，再勾选写入飞书，把真实素材保存到素材表或云文档。</p>"
    if action == "search":
        return "<p>搜索结果已生成。先看本地索引里的排序和分类是否符合你的选题判断；如果是抓爆款，排序只会使用公开搜索结果里能看到的阅读、点赞、收藏、评论、播放等线索，不会绕过平台限制去拿私域数据。</p>"
    if action == "dashboard":
        return "<p>看板已生成。回到面板左侧打开本地看板；如果数据结构没问题，再连接真实指标文件或飞书指标表。</p>"
    if action == "rss":
        return "<p>RSS 内容已整理。先检查输出是否符合预期；确认后再决定是否写入飞书内容表。</p>"
    return "<p>这一步已经完成。可以回到面板继续处理真实网页、文件或搜索主题。</p>"


def env_summary_cards(stdout_raw: str, stderr_raw: str, ok: bool) -> str:
    text = f"{stdout_raw}\n{stderr_raw}"
    cards: list[tuple[str, str, str, str]] = []
    if ok:
        cards.append(("ok", "基础环境可用", "当前依赖检查通过。下一步可以先跑样例，或者开始整理真实网页、文件和选题。", "继续使用面板"))
    if "[MISSING]" in text or "存在缺失依赖" in text:
        cards.append(("bad", "有组件还没装全", "这会影响部分采集、文件转换或飞书写入。普通用户不需要自己处理命令，直接让 Agent 自动补齐依赖。", "对 Agent 说：帮我补齐这个项目的依赖"))
    if "未找到 config.json" in text:
        cards.append(("bad", "还没有项目配置", "没有配置文件时，面板仍能跑安全样例和部分本地预览；但写入飞书、真实归档和定时任务还不能正式启用。", "让 Agent 根据模板创建 config.json"))
    if "lark-cli" in text and "[MISSING] lark-cli" in text:
        cards.append(("bad", "飞书连接工具未就绪", "写入飞书需要先安装并登录飞书 CLI。没配好之前，面板会继续保持本地预览，不会写入飞书。", "让 Agent 帮你安装并登录飞书 CLI"))
    if "renhua" in text and "[MISSING] renhua" in text:
        cards.append(("warn", "去 AI 味润色未就绪", "这不影响采集和看板，只会影响自动摘要、通知文案的润色效果。", "可以稍后再补"))
    if not cards:
        cards.append(("warn", "需要 Agent 看一下详细记录", "脚本没有返回清晰的用户提示。下面的详细记录是给 Agent 判断问题用的。", "展开详细记录"))

    html_cards = []
    for kind, title, body, action in cards:
        html_cards.append(f"""
    <div class="summary-card {kind}">
      <strong>{html.escape(title)}</strong>
      <p>{html.escape(body)}</p>
      <span>{html.escape(action)}</span>
    </div>""")
    return "<div class=\"summary-grid\">" + "".join(html_cards) + "\n  </div>"


def parse_json_from_output(text: str) -> dict:
    stripped = text.strip()
    if not stripped:
        return {}
    for line in reversed(stripped.splitlines()):
        item = line.strip()
        if item.startswith("{") and item.endswith("}"):
            try:
                return json.loads(item)
            except json.JSONDecodeError:
                pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return {}
    return {}


def output_href(raw_path: str) -> str:
    if not raw_path:
        return ""
    try:
        target = Path(raw_path).resolve()
        rel = target.relative_to(PANEL_OUTPUT.resolve())
    except (OSError, ValueError):
        return ""
    return "/output/" + rel.as_posix() if target.is_file() else ""


def summary_card(kind: str, title: str, body: str, action: str = "", href: str = "") -> str:
    footer = ""
    if href and action:
        footer = f'<a class="secondary-link" href="{html.escape(href)}">{html.escape(action)}</a>'
    elif action:
        footer = f"<span>{html.escape(action)}</span>"
    return f"""
    <div class="summary-card {html.escape(kind)}">
      <strong>{html.escape(title)}</strong>
      <p>{html.escape(body)}</p>
      {footer}
    </div>"""


def link_card(title: str, body: str, href: str = "", action: str = "") -> str:
    return summary_card("ok", title, body, action, href)


def failure_summary_cards(action: str, text: str) -> str:
    cards: list[str] = []
    if action == "material" and ("请填写素材内容" in text or "请指定" in text):
        cards.append(summary_card("bad", "还没给材料", "先放入一个网页链接、本地文件路径或一段文本。你也可以让 Agent 帮你选择文件后再运行。", "返回 03 补充材料"))
    elif action == "search" and "请先写下要采集的选题清单" in text:
        cards.append(summary_card("bad", "还没写采集清单", "这里需要一行一个选题，比如“B 站 Agent 运营”或“小红书 内容自动化案例”。", "返回 04 写选题"))
    elif action == "rss" and ("请填写 RSS 地址" in text or "请指定 --rss-url" in text):
        cards.append(summary_card("bad", "还没填订阅地址", "RSS 适合固定来源自动归档。先填一个公开 RSS / Atom 地址，再决定是否写入飞书。", "返回 05 填地址"))
    elif action == "search" and "没有任何可用的搜索后端" in text:
        cards.append(summary_card("bad", "采集渠道还没接上", "当前没有可用的搜索后端，所以还不能按选题采集。普通用户不用处理安装细节，把详细记录交给 Agent 补齐。", "让 Agent 修复采集渠道"))
    elif "运行时间超过" in text or "命令超时" in text:
        if action == "search":
            cards.append(summary_card("warn", "采集等待太久，已停止", "外部搜索或网站响应太慢。可以减少选题数量、换采集范围，或让 Agent 接手做深度采集。", "先缩小范围，再重试"))
        elif action == "material":
            cards.append(summary_card("warn", "材料处理等太久，已停止", "可能是网页打开慢、文件太大，或模型服务响应慢。可以先换一份小材料测试，或让 Agent 单独处理这个文件。", "让 Agent 接手排查"))
        else:
            cards.append(summary_card("warn", "这一步等待太久，已停止", "外部服务或本机组件响应太慢。先不要重复点击，把详细记录交给 Agent 判断下一步。", "让 Agent 根据详细记录处理"))
    elif "No module named 'feedparser'" in text or "feedparser 未安装" in text:
        cards.append(summary_card("bad", "RSS 解析组件没装好", "搜索以外的订阅归档需要一个 RSS 解析组件。普通用户不用自己安装，把详细记录交给 Agent 补齐依赖。", "让 Agent 补齐 Python 依赖"))
    elif "No module named 'pandas'" in text:
        cards.append(summary_card("bad", "看板组件没装好", "生成数据看板需要表格分析组件。普通用户不用自己安装，让 Agent 补齐依赖后再点 06。", "让 Agent 补齐 Python 依赖"))
    elif "No module named 'bs4'" in text:
        cards.append(summary_card("bad", "网页读取组件没装好", "整理网页链接需要网页解析组件。普通用户不用自己安装，让 Agent 补齐依赖后再点 03。", "让 Agent 补齐 Python 依赖"))
    elif "No module named 'markitdown'" in text or "markitdown 未安装" in text:
        cards.append(summary_card("bad", "文件转换组件没装好", "整理 PDF、Word、PPT、表格等文件需要文件转换组件。普通用户不用自己安装，让 Agent 补齐后再试。", "让 Agent 补齐 Python 依赖"))
    elif action == "rss" and "拒绝不安全" in text:
        cards.append(summary_card("bad", "这个订阅地址不适合自动抓取", "系统拦截了本机地址、内网地址或异常协议，避免误抓私有资源。请换成公开 RSS 地址。", "换一个公开订阅地址"))
    elif action == "dashboard" and ("No such file" in text or "找不到" in text or "不存在" in text):
        cards.append(summary_card("bad", "指标文件没读到", "如果只是想看样子，可以把路径留空，用示例数据生成看板；如果要用真实数据，让 Agent 选择正确文件。", "返回 06 修改文件"))
    elif "请填写" in text:
        cards.append(summary_card("bad", "还缺一项必填内容", "回到面板，把这一项补上再运行。具体缺什么可以展开详细记录给 Agent 看。", "返回面板修改输入"))
    else:
        cards.append(summary_card("bad", "这一步没有完成", "先不要写入飞书。展开详细记录，把内容交给 Agent 继续排查。", "让 Agent 根据详细记录修复"))
    return "<div class=\"summary-grid\">" + "".join(cards) + "\n  </div>"


def generic_summary_cards(action: str, stdout_raw: str, stderr_raw: str, ok: bool) -> str:
    text = f"{stdout_raw}\n{stderr_raw}"
    cards: list[str] = []
    if not ok:
        return failure_summary_cards(action, text)

    if action == "offline":
        index = PANEL_OUTPUT / "offline-demo" / "index.md"
        cards.append(link_card(
            "样例已经生成",
            "系统用内置文章生成了本地索引和示例 Markdown，没有联网，也没有写入飞书。",
            "/output/offline-demo/index.md" if index.exists() else "",
            "打开样例结果" if index.exists() else "",
        ))
        cards.append("""
    <div class="summary-card ok">
      <strong>下一步处理真实材料</strong>
      <p>看懂样例结果后，可以回到面板粘贴网页、上传文件，或按选题去采集公开内容。</p>
      <span>推荐继续用 03 或 04</span>
    </div>""")
    elif action == "material":
        data = parse_json_from_output(stdout_raw)
        result = (data.get("results") or [{}])[0] if isinstance(data.get("results"), list) else {}
        href = output_href(str(result.get("md", "")))
        count = int(data.get("count") or 0) if isinstance(data, dict) else 0
        cards.append(link_card(
            "材料已经整理",
            f"这次处理了 {count or 1} 份材料，已生成本地 Markdown。先看摘要、标签和复用建议是否可用。",
            href,
            "打开整理结果" if href else "",
        ))
        cards.append(summary_card("ok", "下一步再决定是否同步", "默认只是本地预览。确认内容没问题后，再勾选写入飞书素材表或云文档。", "先预览，再同步"))
    elif action == "search":
        data = parse_json_from_output(stdout_raw)
        count = int(data.get("count") or 0) if isinstance(data, dict) else 0
        href = output_href(str(data.get("index", ""))) if isinstance(data, dict) else ""
        if count:
            cards.append(link_card(
                "选题采集完成",
                f"这次整理出 {count} 条结果。先看标题、排序和分组是否符合你的选题判断。",
                href,
                "打开采集索引" if href else "",
            ))
            cards.append(summary_card("ok", "爆款排序只看公开线索", "阅读、点赞、收藏、评论、播放等排序依据只来自公开可见内容，不绕过平台限制。", "确认后再写入飞书归档表"))
        else:
            cards.append(summary_card("warn", "没有找到可用结果", "流程跑完了，但这次没有采到内容。可以换选题、缩小来源范围，或让 Agent 检查采集渠道。", "调整 04 后再试"))
    elif action == "rss":
        data = parse_json_from_output(stdout_raw)
        written = int(data.get("written") or 0) if isinstance(data, dict) else 0
        href = output_href(str(data.get("backup", ""))) if isinstance(data, dict) else ""
        if written:
            cards.append(link_card(
                "订阅内容已整理",
                f"这次从订阅源整理出 {written} 条内容，并生成了本地备份。",
                href,
                "打开订阅备份" if href else "",
            ))
            cards.append(summary_card("ok", "适合做自动归档", "确认来源稳定后，可以让 Agent 按每天或每周节奏创建自动任务。", "确认后再写入飞书内容表"))
        else:
            cards.append(summary_card("warn", "这次没有新增内容", "订阅源能访问，但没有抓到可归档的新条目。可以换 RSS 地址，或稍后再跑。", "适合后续定时检查"))
    elif action == "dashboard":
        data = parse_json_from_output(stdout_raw)
        summary = data.get("summary", {}) if isinstance(data, dict) else {}
        dash_path = str(data.get("dashboard", "")) if isinstance(data, dict) else ""
        href = output_href(dash_path) or ("/output/dashboard.html" if (PANEL_OUTPUT / "dashboard.html").exists() else "")
        reads = summary.get("total_reads")
        rate = summary.get("engagement_rate")
        note = "如果没有填真实数据文件，这次使用的是示例数据，只用于预览报表样式。"
        if reads is not None and rate is not None:
            note = f"看板已汇总 {reads} 次阅读 / 播放，互动率约 {float(rate) * 100:.2f}%。先确认报表结构是否符合你的日常查看习惯。"
        cards.append(link_card(
            "看板已经生成",
            note,
            href,
            "打开本地看板" if href else "",
        ))
        cards.append(summary_card("ok", "定时任务还没有真正创建", "面板只负责验证看板能生成。每天或每周自动运行，需要让 Agent 按你的节奏创建系统任务。", "确认流程后再设置自动化"))
    else:
        cards.append("""
    <div class="summary-card ok">
      <strong>这一步已经完成</strong>
      <p>先检查本地产物，确认没问题后再决定是否写入飞书或设置定时任务。</p>
      <span>继续回到面板</span>
    </div>""")
    return "<div class=\"summary-grid\">" + "".join(cards) + "\n  </div>"


def result_summary(action: str, stdout_raw: str, stderr_raw: str, ok: bool) -> str:
    if action == "env":
        return env_summary_cards(stdout_raw, stderr_raw, ok)
    return generic_summary_cards(action, stdout_raw, stderr_raw, ok)


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#11151d">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg:#f5f7fb;
      --ink:#182033;
      --muted:#687386;
      --subtle:#8a95a7;
      --line:#dce2ec;
      --panel:#ffffff;
      --panel-soft:#f9fbfe;
      --nav:#11151d;
      --nav-2:#171d28;
      --blue:#2d65d8;
      --blue-soft:#e8efff;
      --green:#1f7a56;
      --green-soft:#e5f5ee;
      --amber:#a15c00;
      --amber-soft:#fff3df;
      --red:#b84a4a;
      --red-soft:#fff0f0;
      --shadow:0 10px 28px rgba(20,31,52,.08),0 1px 0 rgba(20,31,52,.04);
      --ease-out:cubic-bezier(.23,1,.32,1);
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",sans-serif;
      letter-spacing:0;
      color:var(--ink);
      background:
        linear-gradient(180deg,#eef3fb 0,#f5f7fb 220px),
        var(--bg);
    }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    header {{
      background:linear-gradient(180deg,var(--nav) 0,var(--nav-2) 100%);
      border-bottom:1px solid rgba(255,255,255,.08);
      color:#f7f9fc;
    }}
    .topbar {{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:16px;
      max-width:1220px;
      margin:0 auto;
      padding:16px 24px;
      border-bottom:1px solid rgba(255,255,255,.08);
    }}
    .brand {{
      display:flex;
      align-items:center;
      gap:10px;
      min-width:0;
      font-weight:600;
    }}
    .mark {{
      display:grid;
      place-items:center;
      width:32px;
      height:32px;
      border-radius:8px;
      background:#f7f9fc;
      color:var(--nav);
      box-shadow:inset 0 -1px 0 rgba(17,21,29,.16);
      font:700 14px/1 ui-monospace,SFMono-Regular,Consolas,monospace;
    }}
    .safe-pill {{
      display:inline-flex;
      align-items:center;
      gap:8px;
      border:1px solid rgba(255,255,255,.12);
      border-radius:999px;
      padding:7px 12px;
      color:rgba(255,255,255,.84);
      background:rgba(255,255,255,.04);
      white-space:nowrap;
    }}
    .safe-pill::before {{
      content:"";
      width:8px;
      height:8px;
      border-radius:50%;
      background:#45d483;
      box-shadow:0 0 0 4px rgba(69,212,131,.12);
    }}
    .masthead {{
      max-width:1220px;
      margin:0 auto;
      padding:34px 24px 38px;
      display:grid;
      grid-template-columns:minmax(0,1.1fr) minmax(280px,.9fr);
      gap:28px;
      align-items:end;
    }}
    h1 {{
      margin:0 0 12px;
      font-size:34px;
      line-height:1.2;
      font-weight:600;
      text-wrap:balance;
    }}
    .lead {{
      max-width:58em;
      margin:0;
      color:rgba(255,255,255,.72);
      line-height:1.75;
    }}
    .quick-status {{
      display:grid;
      grid-template-columns:repeat(3,minmax(0,1fr));
      gap:10px;
      min-width:0;
    }}
    .mini {{
      min-height:86px;
      padding:12px;
      border-radius:8px;
      background:rgba(255,255,255,.05);
      border:1px solid rgba(255,255,255,.1);
    }}
    .mini span {{
      display:block;
      color:rgba(255,255,255,.56);
      font-size:12px;
    }}
    .mini strong {{
      display:block;
      margin-top:8px;
      font-size:18px;
      font-weight:600;
      color:#f7f9fc;
    }}
    main {{
      max-width:1220px;
      margin:0 auto;
      padding:24px;
    }}
    .layout {{
      display:grid;
      grid-template-columns:320px minmax(0,1fr);
      gap:18px;
      align-items:start;
    }}
    section {{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:8px;
      box-shadow:var(--shadow);
    }}
    .panel {{
      padding:18px;
    }}
    .side-rail {{
      position:sticky;
      top:18px;
      display:grid;
      gap:16px;
      align-content:start;
      min-width:0;
    }}
    .status-panel {{
      overflow:hidden;
    }}
    .section-title {{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin:0 0 14px;
    }}
    h2 {{
      margin:0;
      font-size:18px;
      line-height:1.35;
      font-weight:600;
      text-wrap:balance;
    }}
    h3 {{
      margin:0;
      font-size:16px;
      line-height:1.45;
      font-weight:600;
    }}
    p {{ margin:0 0 12px; }}
    .muted {{ color:var(--muted); }}
    .note {{ color:var(--muted); font-size:14px; line-height:1.65; }}
    .hint {{
      color:var(--subtle);
      font-size:13px;
      line-height:1.55;
    }}
    .flow-map {{
      margin-bottom:18px;
      padding:16px 18px;
      display:grid;
      gap:12px;
    }}
    .flow-steps {{
      display:grid;
      grid-template-columns:repeat(4,minmax(0,1fr));
      gap:10px;
      margin:0;
      padding:0;
      list-style:none;
    }}
    .flow-steps li {{
      min-width:0;
      padding:12px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel-soft);
    }}
    .flow-steps strong {{
      display:block;
      font-size:14px;
      line-height:1.35;
    }}
    .flow-steps span {{
      display:block;
      margin-top:4px;
      color:var(--muted);
      font-size:13px;
      line-height:1.5;
    }}
    .status-list {{
      display:grid;
      gap:10px;
      margin:0;
    }}
    .status-item {{
      display:grid;
      gap:5px;
      padding:12px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel-soft);
      min-width:0;
    }}
    .status-item dt {{
      color:var(--subtle);
      font-size:12px;
      margin:0;
    }}
    .status-item dd {{
      margin:0;
      min-width:0;
      overflow-wrap:anywhere;
    }}
    .badge {{
      display:inline-flex;
      align-items:center;
      gap:7px;
      min-height:28px;
      padding:4px 9px;
      border-radius:999px;
      font-weight:600;
      font-size:13px;
    }}
    .badge.ok {{ background:var(--green-soft); color:var(--green); }}
    .badge.bad {{ background:var(--red-soft); color:var(--red); }}
    .badge.info {{ background:var(--blue-soft); color:var(--blue); }}
    .workflows {{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:16px;
      align-items:start;
    }}
    .workflow-column {{
      display:grid;
      gap:16px;
      align-content:start;
      min-width:0;
    }}
    .workflow {{
      --flow-rgb:45,101,216;
      position:relative;
      display:flex;
      flex-direction:column;
      padding:18px;
      overflow:hidden;
      background:
        linear-gradient(135deg,rgba(var(--flow-rgb),.055),rgba(255,255,255,0) 42%),
        var(--panel);
      transition:transform 180ms var(--ease-out),border-color 180ms var(--ease-out),box-shadow 180ms var(--ease-out),background-color 180ms var(--ease-out);
    }}
    .workflow::before {{
      content:"";
      position:absolute;
      inset:0 auto 0 0;
      width:3px;
      background:linear-gradient(180deg,rgba(var(--flow-rgb),.86),rgba(var(--flow-rgb),.18));
      opacity:.72;
    }}
    .flow-env {{ --flow-rgb:45,101,216; }}
    .flow-sample {{ --flow-rgb:31,122,86; }}
    .flow-material {{ --flow-rgb:161,92,0; }}
    .flow-search {{ --flow-rgb:45,101,216; }}
    .flow-rss {{ --flow-rgb:111,77,191; }}
    .flow-dashboard {{ --flow-rgb:184,74,74; }}
    .workflow:focus-within {{
      border-color:rgba(var(--flow-rgb),.42);
      box-shadow:0 0 0 4px rgba(var(--flow-rgb),.1),var(--shadow);
    }}
    .workflow-head {{
      display:flex;
      align-items:flex-start;
      gap:12px;
      margin-bottom:12px;
    }}
    .step {{
      flex:0 0 auto;
      display:grid;
      place-items:center;
      width:32px;
      height:32px;
      border-radius:8px;
      background:rgba(var(--flow-rgb),.1);
      color:rgb(var(--flow-rgb));
      font:700 13px/1 ui-monospace,SFMono-Regular,Consolas,monospace;
      box-shadow:inset 0 -1px 0 rgba(var(--flow-rgb),.14);
      transition:transform 180ms var(--ease-out),background-color 180ms var(--ease-out);
    }}
    form {{
      display:grid;
      gap:11px;
      margin-top:14px;
    }}
    label {{
      display:grid;
      gap:6px;
      color:#30394c;
      font-weight:600;
    }}
    input, textarea, select {{
      width:100%;
      border:1px solid var(--line);
      border-radius:6px;
      padding:10px 11px;
      background:#fff;
      color:var(--ink);
      font:inherit;
      line-height:1.45;
      outline:2px solid transparent;
      outline-offset:1px;
      transition:border-color 160ms var(--ease-out),box-shadow 160ms var(--ease-out),background-color 160ms var(--ease-out);
    }}
    textarea {{
      min-height:92px;
      resize:vertical;
    }}
    .category-map {{
      min-height:68px;
    }}
    .task-list {{
      min-height:112px;
    }}
    .field-row {{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:10px;
    }}
    .soft-box {{
      display:grid;
      gap:8px;
      padding:12px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel-soft);
    }}
    .soft-box strong {{
      font-size:14px;
      line-height:1.35;
      font-weight:600;
    }}
    .soft-box p {{
      margin:0;
      color:var(--muted);
      font-size:13px;
      line-height:1.55;
    }}
    details.inline-options {{
      margin-top:0;
      padding:10px 12px;
    }}
    details.inline-options textarea {{
      margin-top:8px;
    }}
    input::placeholder, textarea::placeholder {{ color:#9aa5b5; }}
    input:focus-visible, textarea:focus-visible, select:focus-visible {{
      border-color:#7da0f3;
      box-shadow:0 0 0 4px rgba(45,101,216,.14);
    }}
    .check {{
      display:flex;
      align-items:center;
      gap:9px;
      width:fit-content;
      max-width:100%;
      color:var(--muted);
      font-weight:500;
      cursor:pointer;
    }}
    .check input {{
      width:16px;
      height:16px;
      padding:0;
      accent-color:var(--blue);
    }}
    button {{
      justify-self:start;
      min-height:40px;
      border:0;
      border-radius:6px;
      padding:10px 14px;
      background:var(--blue);
      color:white;
      font-family:inherit;
      font-size:14px;
      line-height:1.2;
      font-weight:600;
      cursor:pointer;
      box-shadow:0 1px 0 rgba(255,255,255,.22) inset,0 8px 18px rgba(45,101,216,.18);
      transition:transform 140ms var(--ease-out),background-color 160ms var(--ease-out),box-shadow 160ms var(--ease-out);
    }}
    button:hover {{ background:#2459c6; box-shadow:0 1px 0 rgba(255,255,255,.22) inset,0 10px 22px rgba(45,101,216,.22); }}
    button:active {{ transform:scale(.98); }}
    button:focus-visible {{
      outline:2px solid rgba(45,101,216,.42);
      outline-offset:3px;
    }}
    .secondary-link {{
      display:inline-flex;
      align-items:center;
      gap:8px;
      min-height:34px;
      padding:7px 10px;
      border:1px solid var(--line);
      border-radius:6px;
      background:#fff;
      color:var(--ink);
      font-weight:600;
    }}
    .secondary-link:hover {{
      text-decoration:none;
      border-color:#b9c7df;
      background:var(--panel-soft);
    }}
    code, pre {{
      font-family:ui-monospace,SFMono-Regular,Consolas,monospace;
      font-variant-numeric:tabular-nums;
    }}
    code {{
      padding:2px 5px;
      border-radius:4px;
      background:#eef2f7;
    }}
    pre {{
      white-space:pre-wrap;
      overflow:auto;
      max-height:340px;
      margin:10px 0 0;
      padding:14px;
      border-radius:8px;
      background:#11151d;
      color:rgba(255,255,255,.86);
      border:1px solid rgba(255,255,255,.08);
    }}
    .result {{
      max-width:1120px;
      margin:0 auto;
      padding:20px;
    }}
    .result-line {{
      display:flex;
      align-items:center;
      gap:10px;
      flex-wrap:wrap;
      margin:12px 0 16px;
    }}
    .result-grid {{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:14px;
      align-items:stretch;
    }}
    .result-pane {{
      display:flex;
      min-width:0;
      flex-direction:column;
    }}
    .result-pane pre {{
      flex:1;
      min-height:320px;
      max-height:52vh;
    }}
    .summary-grid {{
      display:grid;
      grid-template-columns:repeat(2,minmax(0,1fr));
      gap:12px;
      margin-top:14px;
    }}
    .summary-card {{
      display:grid;
      gap:7px;
      min-width:0;
      padding:14px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel-soft);
    }}
    .summary-card strong {{
      font-size:15px;
      line-height:1.35;
      font-weight:600;
    }}
    .summary-card p {{
      margin:0;
      color:var(--muted);
      font-size:14px;
      line-height:1.65;
    }}
    .summary-card span {{
      color:var(--ink);
      font-size:13px;
      font-weight:600;
    }}
    .summary-card.ok {{ border-color:#bfe5d3; background:var(--green-soft); }}
    .summary-card.bad {{ border-color:#f0c3c3; background:var(--red-soft); }}
    .summary-card.warn {{ border-color:#efd4a9; background:var(--amber-soft); }}
    details {{
      margin-top:16px;
      border:1px solid var(--line);
      border-radius:8px;
      background:var(--panel-soft);
      padding:12px;
    }}
    summary {{
      cursor:pointer;
      font-weight:600;
    }}
    @media (hover:hover) and (pointer:fine) {{
      .workflow:hover {{
        transform:translateY(-2px);
        border-color:rgba(var(--flow-rgb),.34);
        box-shadow:0 16px 36px rgba(20,31,52,.12),0 1px 0 rgba(20,31,52,.04);
      }}
      .workflow:hover .step {{ transform:translateY(-1px); background:rgba(var(--flow-rgb),.15); }}
    }}
    @media (prefers-reduced-motion:reduce) {{
      *,*::before,*::after {{
        transition-duration:1ms !important;
        animation-duration:1ms !important;
      }}
    }}
    @media (max-width:920px) {{
      .masthead {{ grid-template-columns:1fr; }}
      .layout {{ grid-template-columns:1fr; }}
      .side-rail {{ position:static; }}
      .flow-steps {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      .workflows {{ grid-template-columns:1fr; }}
      .summary-grid {{ grid-template-columns:1fr; }}
      .result-grid {{ grid-template-columns:1fr; }}
      .result-pane pre {{ min-height:260px; max-height:420px; }}
    }}
    @media (max-width:620px) {{
      .topbar {{ align-items:flex-start; flex-direction:column; }}
      .masthead {{ padding:28px 18px; }}
      h1 {{ font-size:28px; }}
      main {{ padding:18px; }}
      .quick-status {{ grid-template-columns:1fr; }}
      .flow-steps {{ grid-template-columns:1fr; }}
      .field-row {{ grid-template-columns:1fr; }}
    }}
  </style>
</head>
<body>
<header>
  <div class="topbar">
    <div class="brand"><span class="mark">ML</span><span>Media Automation Lark</span></div>
    <div class="safe-pill">默认只预览，本地输出优先</div>
  </div>
  <div class="masthead">
    <div>
      <h1>{html.escape(title)}</h1>
      <p class="lead">把网页、文件、搜索选题、RSS 更新和数据看板放进一个本地工作台。先在本机预览结果，确认没问题后再写入飞书或交给 Agent 设置定时任务。</p>
    </div>
    <div class="quick-status" aria-label="关键状态">
      <div class="mini"><span>运行位置</span><strong>本机</strong></div>
      <div class="mini"><span>默认模式</span><strong>先预览</strong></div>
      <div class="mini"><span>飞书写入</span><strong>手动开启</strong></div>
    </div>
  </div>
</header>
<main>{body}</main>
</body>
</html>""".encode("utf-8")


def render_home() -> bytes:
    ensure_panel_config()
    cfg = project_config()
    lark = shutil.which("lark-cli")
    dash = PANEL_OUTPUT / "dashboard.html"
    index = PANEL_OUTPUT / "offline-demo" / "index.md"
    status = f"""
<section class="status-panel panel" aria-labelledby="status-title">
  <div class="section-title">
    <h2 id="status-title">状态</h2>
    {'<span class="badge ok">飞书 CLI 已就绪</span>' if lark else '<span class="badge bad">未检测到 lark-cli</span>'}
  </div>
  <dl class="status-list">
    <div class="status-item"><dt>配置文件</dt><dd><code>{html.escape(str(cfg))}</code></dd></div>
    <div class="status-item"><dt>输出目录</dt><dd><code>{html.escape(str(PANEL_OUTPUT))}</code></dd></div>
    <div class="status-item"><dt>本地看板</dt><dd>{'<a class="secondary-link" href="/output/dashboard.html">打开 dashboard.html</a>' if dash.exists() else '<span class="muted">尚未生成</span>'}</dd></div>
    <div class="status-item"><dt>样例结果</dt><dd>{'<a class="secondary-link" href="/output/offline-demo/index.md">打开样例结果</a>' if index.exists() else '<span class="muted">尚未生成</span>'}</dd></div>
  </dl>
</section>
"""
    env_card = """
<section class="workflow flow-env">
  <div class="workflow-head"><span class="step">01</span><div><h3>先检查能不能跑</h3><p class="note">一次看清依赖、飞书 CLI、搜索后端和配置是否准备好。</p></div></div>
  <form method="post" action="/run/env"><button type="submit">检查现在状态</button></form>
</section>
"""
    forms = f"""
<div class="layout">
  <aside class="side-rail">
    {status}
    {env_card}
  </aside>
  <div>
  <section class="flow-map" aria-labelledby="flow-title">
    <h2 id="flow-title">从输入到归档</h2>
    <ul class="flow-steps">
      <li><strong>1. 给材料</strong><span>贴网页、丢文件、填 RSS，或写一组选题。</span></li>
      <li><strong>2. 本地预览</strong><span>先生成 Markdown、看板或索引，不直接写飞书。</span></li>
      <li><strong>3. 人来判断</strong><span>看分类、摘要、排序和日志，确认是否值得入库。</span></li>
      <li><strong>4. 再同步</strong><span>确认后勾选写入飞书，定时任务交给 Agent 配置。</span></li>
    </ul>
  </section>
  <div class="workflows">
  <div class="workflow-column">
  <section class="workflow flow-sample">
    <div class="workflow-head"><span class="step">02</span><div><h3>先体验一次完整流程</h3><p class="note">第一次不知道怎么用时点这里。系统用内置样例跑一遍，让你先看到结果长什么样；不联网、不写飞书。</p></div></div>
    <form method="post" action="/run/offline">
      <div class="soft-box">
        <strong>不用填写任何东西</strong>
        <p>这一步只做安全样例，生成一个本地索引和两篇示例 Markdown。看懂输出后，再去处理真实网页、文件或选题。</p>
      </div>
      <button type="submit">先体验一下</button>
    </form>
  </section>
  <section class="workflow flow-material">
    <div class="workflow-head"><span class="step">03</span><div><h3>直接丢网页或文件</h3><p class="note">适合已经有明确材料：网页链接、本地文件，或一段临时文本。</p></div></div>
    <form method="post" action="/run/material">
      <label>我手上的是
      <select name="material_type"><option value="url">网页链接</option><option value="file">本地文件</option><option value="text">文本片段</option></select>
      </label>
      <label>粘贴链接 / 填文件路径 / 放入文本
      <textarea name="material_value" placeholder="例如：https://example.com/article  或  E:\\素材\\report.pdf"></textarea>
      </label>
      <label class="check"><input type="checkbox" name="write_feishu"> 确认后写入飞书素材表 / 云文档</label>
      <button type="submit">整理这份材料</button>
    </form>
  </section>
  <section class="workflow flow-dashboard">
    <div class="workflow-head"><span class="step">06</span><div><h3>看板和定时</h3><p class="note">想先看看报表长什么样，直接点生成看板；有真实数据文件时再填路径。</p></div></div>
    <form method="post" action="/run/dashboard">
      <label>已有数据文件（可留空）
      <input name="source" placeholder="可留空，或粘贴 E:\\\\数据\\\\metrics.json">
      <span class="hint">留空会自动使用示例数据，只生成本地 dashboard.html，不会写入飞书。</span>
      </label>
      <label>想要的定时节奏
      <select name="schedule_hint"><option>先手动跑一次</option><option>每天自动跑</option><option>每周自动跑</option></select>
      <span class="hint">面板先验证结果；自动定时需要 Agent 按你的选择创建系统任务。</span>
      </label>
      <label class="check"><input type="checkbox" name="write_feishu"> 确认后写入飞书指标表</label>
      <button type="submit">生成看板</button>
    </form>
  </section>
  </div>
  <div class="workflow-column">
  <section class="workflow flow-search">
    <div class="workflow-head"><span class="step">04</span><div><h3>按选题去采集</h3><p class="note">适合找资料、找爆款、找竞品内容。先快速生成候选索引，再决定要不要抓全文和写入飞书。</p></div></div>
    <form method="post" action="/run/search">
      <div class="field-row">
        <label>主要去哪里找
        <select name="source_scope">{option_tags(SOURCE_SCOPES)}</select>
        </label>
        <label>优先怎么看结果
        <select name="rank_by">{option_tags(RANK_MODES)}</select>
        </label>
      </div>
      <label>采集清单（一行一个选题）
      <textarea class="task-list" name="query" placeholder="AI 视频工作流爆款案例&#10;小红书 内容自动化 教程&#10;B 站 Agent 运营"></textarea>
      </label>
      <label>只看某个网站 / 作者 / 账号（可空）
      <input name="source_filter" placeholder="例如：mp.weixin.qq.com、某个作者名、某个栏目名">
      </label>
      <div class="field-row">
        <label>分组方式
        <select name="category_preset">{option_tags(CATEGORY_OPTIONS)}</select>
        <span class="hint">选择结果保存时的目录。不会影响搜索，只影响整理后的分类。</span>
        </label>
        <label>每个选题最多保留
        <input name="max_per_query" type="number" min="1" max="20" value="5">
        <span class="hint">爆款排序会尽量参考公开可见的阅读、点赞、收藏、评论、播放等线索。</span>
        </label>
      </div>
      <details class="inline-options">
        <summary>需要自己定义分组时再打开</summary>
        <textarea class="category-map" name="custom_category_map" placeholder="例如：AI:大模型,Agent;产品:增长,运营"></textarea>
      </details>
      <label class="check"><input type="checkbox" name="write_feishu"> 确认后写入飞书归档表</label>
      <button type="submit">开始采集选题</button>
    </form>
  </section>
  <section class="workflow flow-rss">
    <div class="workflow-head"><span class="step">05</span><div><h3>订阅源自动归档</h3><p class="note">适合固定来源的更新：博客、媒体、产品公告、RSS 订阅。</p></div></div>
    <form method="post" action="/run/rss">
      <label>RSS 地址
      <input name="rss_url" placeholder="https://example.com/feed.xml">
      </label>
      <label>最多取几条
      <input name="limit" value="10">
      </label>
      <label class="check"><input type="checkbox" name="write_feishu"> 确认后写入飞书内容表</label>
      <button type="submit">整理订阅更新</button>
    </form>
  </section>
  </div>
  </div>
  </div>
</div>
"""
    return page("本地自动化控制台", forms)


def render_result(result: dict[str, object]) -> bytes:
    rc = int(result["returncode"])
    cmd = " ".join(str(c) for c in result["cmd"])
    stdout_raw = str(result.get("stdout") or "")
    stderr_raw = str(result.get("stderr") or "")
    stdout = html.escape(stdout_raw or "没有标准输出。")
    stderr = html.escape(stderr_raw or "没有日志或错误。")
    action = str(result.get("action") or "")
    guidance = next_steps(action, rc == 0)
    summary = result_summary(action, stdout_raw, stderr_raw, rc == 0)
    body = f"""
<section class="result panel" role="status" aria-live="polite">
  <h2>{html.escape(str(result['title']))}</h2>
  <div class="result-line">
    {'<span class="badge ok">成功</span>' if rc == 0 else '<span class="badge bad">失败</span>'}
    <span class="muted">退出码：<code>{rc}</code></span>
    <a class="secondary-link" href="/">返回面板</a>
  </div>
  <dl class="status-list">
    <div class="status-item">
      <dt>下一步</dt>
      <dd>{guidance}</dd>
    </div>
  </dl>
  <h2>检查结果</h2>
  {summary}
  <details>
    <summary>详细记录（给 Agent 排查用）</summary>
    <div class="result-grid">
      <div class="result-pane">
        <h2>脚本输出</h2>
        <pre>{stdout}</pre>
      </div>
      <div class="result-pane">
        <h2>日志 / 错误</h2>
        <pre>{stderr}</pre>
      </div>
    </div>
    <pre>{html.escape(cmd)}</pre>
  </details>
</section>
"""
    return page("运行结果", body)


class Handler(BaseHTTPRequestHandler):
    def send_html(self, content: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_html(render_home())
            return
        if parsed.path.startswith("/output/"):
            self.serve_output(parsed.path[len("/output/"):])
            return
        self.send_html(page("Not Found", "<section><p>页面不存在。</p></section>"), 404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/run/"):
            self.send_html(page("Not Found", "<section><p>页面不存在。</p></section>"), 404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(raw)
        action = parsed.path.rsplit("/", 1)[-1]
        try:
            result = run_action(action, form)
        except Exception as exc:  # noqa: BLE001
            result = {"action": action, "title": action_title(action), "cmd": [], "returncode": 1, "stdout": "", "stderr": str(exc)}
        self.send_html(render_result(result))

    def serve_output(self, raw_rel: str) -> None:
        rel = unquote(raw_rel).replace("\\", "/").lstrip("/")
        target = (PANEL_OUTPUT / rel).resolve()
        base = PANEL_OUTPUT.resolve()
        try:
            target.relative_to(base)
        except ValueError:
            self.send_html(page("Not Found", "<section class=\"panel\"><p>输出文件不存在。</p></section>"), 404)
            return
        if not target.is_file():
            self.send_html(page("Not Found", "<section class=\"panel\"><p>输出文件不存在。</p></section>"), 404)
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Media Automation Lark 本地控制面板")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--open", action="store_true", help="启动后尝试打开默认浏览器")
    args = parser.parse_args()
    ensure_panel_config()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Media Automation Lark 控制面板: {url}")
    print("按 Ctrl+C 停止。")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")


if __name__ == "__main__":
    main()
