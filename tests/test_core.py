"""纯函数与降级路径的单测。运行：pytest tests/"""
import importlib.util
import os

import pytest

import common
import search_backends as sb
import collector as col


def _load_data_collector():
    p = os.path.join(os.path.dirname(__file__), "..", "scripts", "data-collector.py")
    spec = importlib.util.spec_from_file_location("data_collector", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load_content_archiver():
    p = os.path.join(os.path.dirname(__file__), "..", "scripts", "content-archiver.py")
    spec = importlib.util.spec_from_file_location("content_archiver", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load_gui_panel():
    p = os.path.join(os.path.dirname(__file__), "..", "scripts", "gui-panel.py")
    spec = importlib.util.spec_from_file_location("gui_panel", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _load_panel_agent():
    p = os.path.join(os.path.dirname(__file__), "..", "scripts", "panel-agent.py")
    spec = importlib.util.spec_from_file_location("panel_agent", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---- common.is_safe_url（SSRF 防护）----
def test_is_safe_url():
    assert common.is_safe_url("http://example.com/a")
    assert common.is_safe_url("https://example.com/a")
    assert not common.is_safe_url("file:///etc/passwd")
    assert not common.is_safe_url("ftp://example.com")
    assert not common.is_safe_url("http://127.0.0.1/x")
    assert not common.is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert not common.is_safe_url("http://localhost/x")
    assert not common.is_safe_url("http://10.0.0.1/x")  # 私网默认拦
    assert common.is_safe_url("http://10.0.0.1/x", allow_private=True)


def test_content_archiver_rejects_unsafe_urls():
    ca = _load_content_archiver()
    with pytest.raises(ValueError):
        ca.parse_rss("http://127.0.0.1/feed.xml", 5)
    with pytest.raises(ValueError):
        ca.parse_api("http://169.254.169.254/latest/meta-data/", {}, 5)


# ---- common.validate_config ----
def test_validate_config():
    assert common.validate_config({}) == []
    assert common.validate_config({"llm": {"model": "gpt-4o"}})  # 有 llm 段但缺 key → 告警
    errs = common.validate_config({"feishu": {"app_token": "x"}})
    assert any("table_id" in e for e in errs)


# ---- common.dedup_key ----
def test_dedup_key():
    assert common.dedup_key("HTTP://X.com/A") == "http://x.com/a"


# ---- common.polish_text 降级 ----
def test_polish_disabled():
    assert common.polish_text("原文", {"text": {"polish": False}}) == "原文"


def test_polish_no_key_degrades():
    # 无 LLM key 时原样返回，不抛
    out = common.polish_text("真正重要的是保住判断。", {"text": {"polish": True}, "llm": {}})
    assert out == "真正重要的是保住判断。"


# ---- search_backends 解析 ----def test_parse_anysearch_md():
    md = "### 1. 标题A\n- **URL**: https://a.com/x\n摘要A\n### 2. 标题B\n- **URL**: https://b.com/y"
    r = sb._parse_anysearch_md(md)
    assert len(r) == 2
    assert r[0]["url"] == "https://a.com/x"
    assert r[0]["title"] == "标题A"


def test_coerce_results():
    r = sb._coerce_results([{"url": "https://x.com", "title": "t"}])
    assert r[0]["url"] == "https://x.com"
    assert sb._coerce_results([{"link": "https://y.com"}])[0]["url"] == "https://y.com"
    assert sb._coerce_results([{"no_url": 1}]) == []


# ---- collector 纯函数 ----
def test_category_map():
    assert col.parse_category_map("AI:大模型,LLM;产品:增长") == [("AI", ["大模型", "LLM"]), ("产品", ["增长"])]


def test_classify():
    cm = [("AI", ["大模型", "LLM"]), ("产品", ["增长"])]
    assert col.classify("大模型入门", "", "", cm, "综合") == "AI"
    assert col.classify("随便写", "", "", cm, "综合") == "综合"


def test_safe_name():
    n = col.safe_name("a/b\\c?d:e*e")
    for ch in '\\/:*?"<>|':
        assert ch not in n


# ---- data-collector.compute_metrics ----
def test_compute_metrics():
    dc = _load_data_collector()
    rows = [{"date": "2026-07-06", "platform": "bilibili", "reads": 100, "likes": 10,
             "comments": 5, "shares": 5}]
    s, _ = dc.compute_metrics(rows)
    assert s["total_reads"] == 100
    assert abs(s["engagement_rate"] - 0.2) < 1e-6


def test_gui_panel_builds_safe_default_search_command():
    gp = _load_gui_panel()
    cmd, title = gp.build_command(
        "search",
        {
            "query": ["LLM 应用\nAgent 工作流"],
            "config": ["config.json"],
            "category_map": ["AI:LLM"],
            "max_per_query": ["3"],
            "source_scope": ["bilibili"],
            "rank_by": ["hotness"],
        },
    )
    assert title == "按选题去采集"
    assert "collector.py" in cmd[1]
    assert "--dry-run" in cmd
    assert "--no-archive" in cmd
    assert "--no-fetch" in cmd
    assert cmd.count("--query") == 2
    assert "--source-scope" in cmd
    assert "bilibili" in cmd
    assert "--rank-by" in cmd
    assert "hotness" in cmd


def test_gui_panel_dashboard_uses_source_without_feishu_by_default():
    gp = _load_gui_panel()
    cmd, title = gp.build_command("dashboard", {"source": ["metrics.json"], "config": ["config.json"]})
    assert title == "看板和定时"
    assert "data-collector.py" in cmd[1]
    assert "--source" in cmd
    assert "metrics.json" in cmd
    assert "--dry-run" in cmd
    assert "--push" not in cmd


def test_gui_panel_home_does_not_show_manual_start_command():
    gp = _load_gui_panel()
    html = gp.render_home().decode("utf-8")
    assert "本地自动化控制台" in html
    assert "先体验一次完整流程" in html
    assert "按选题去采集" in html
    assert "主要去哪里找" in html
    assert "不用填写任何东西" in html
    assert "分组方式" in html
    assert "已有数据文件（可留空）" in html
    assert 'name="category_map"' not in html
    assert "不联网、不写飞书" in html
    assert "python scripts/gui-panel.py" not in html


def test_gui_panel_category_preset_keeps_rules_out_of_main_form():
    gp = _load_gui_panel()
    cmd, _ = gp.build_command(
        "search",
        {"query": ["AI 视频"], "category_preset": ["platform"], "max_per_query": ["2"]},
    )
    i = cmd.index("--category-map")
    assert "微信" in cmd[i + 1]
    assert "bilibili" in cmd[i + 1]


def test_gui_panel_result_uses_equal_output_grid():
    gp = _load_gui_panel()
    html = gp.render_result({"action": "offline", "title": "demo", "cmd": [], "returncode": 0, "stdout": "", "stderr": ""}).decode("utf-8")
    assert "result-grid" in html
    assert "result-pane" in html
    assert "没有标准输出" in html
    assert "没有日志或错误" in html
    assert "检查结果" in html
    assert "样例已经生成" in html
    assert "详细记录（给 Agent 排查用）" in html
    assert "下一步" in html
    assert "安全试玩" in html


def test_gui_panel_result_summarizes_all_user_actions():
    gp = _load_gui_panel()
    expectations = {
        "material": ("材料已经整理", '{"ok": true, "count": 1, "results": [{"md": ""}]}'),
        "search": ("选题采集完成", '{"ok": true, "count": 2, "index": ""}'),
        "rss": ("订阅内容已整理", '{"ok": true, "written": 1, "backup": ""}'),
        "dashboard": ("看板已经生成", '{"ok": true, "summary": {"total_reads": 10, "engagement_rate": 0.2}, "dashboard": ""}'),
        "env": "还没有项目配置",
    }
    for action, expected in expectations.items():
        if isinstance(expected, tuple):
            text, stdout = expected
        else:
            text, stdout = expected, "未找到 config.json"
        html = gp.render_result({"action": action, "title": "demo", "cmd": [], "returncode": 0, "stdout": stdout, "stderr": ""}).decode("utf-8")
        assert text in html


def test_collector_scopes_and_ranks_search_results():
    q = col.scoped_query("AI 视频", "bilibili", "")
    assert "site:bilibili.com" in q
    rows = col.rank_results(
        [
            {"title": "普通教程", "url": "https://example.com/a", "snippet": "AI 视频"},
            {"title": "爆款案例", "url": "https://example.com/b", "snippet": "AI 视频 2万点赞 300评论"},
        ],
        "AI 视频",
        "hotness",
        [],
    )
    assert rows[0]["title"] == "爆款案例"
    assert "爆款线索" in rows[0]["rank_note"]


def test_gui_panel_translates_missing_feedparser_for_users():
    gp = _load_gui_panel()
    html = gp.render_result({
        "action": "rss",
        "title": "demo",
        "cmd": [],
        "returncode": 1,
        "stdout": "",
        "stderr": "ModuleNotFoundError: No module named 'feedparser'",
    }).decode("utf-8")
    assert "RSS 解析组件没装好" in html
    assert "让 Agent 补齐 Python 依赖" in html


def test_panel_agent_payload_has_url_and_status():
    pa = _load_panel_agent()
    data = pa.payload("started", "127.0.0.1", 8787, 123, "ok")
    assert data["ok"] is True
    assert data["url"] == "http://127.0.0.1:8787"
    assert data["pid"] == 123
