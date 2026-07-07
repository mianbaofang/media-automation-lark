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
