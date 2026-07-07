"""搜索后端注册表：运行时检测 + 调用适配器。

设计原则（对应"没装就废了"的顾虑）：
- 每个后端相互独立、可选。collector 只用当前可用的后端。
- 缺失的后端被跳过，绝不让整个流程崩溃。
- 每个后端自带 GitHub 安装信息，install_backends.py 据此拉取。

后端分两类：
- SEARCH：给定 query 返回候选 URL 列表（anysearch / tavily / agent_reach / multi_search）
- FETCH：给定 URL 返回 Markdown 正文（autocli / anysearch / tavily / http 兜底）
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REQUESTS_OK = True
try:
    import requests
except Exception:  # pragma: no cover
    REQUESTS_OK = False

BeautifulSoup = None
if REQUESTS_OK:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        BeautifulSoup = None


# --------------------------------------------------------------------------
# 路径 / 工具
# --------------------------------------------------------------------------
def skills_roots() -> list[Path]:
    roots: list[Path] = []
    env = os.environ.get("SKILLS_ROOT")
    if env:
        roots.append(Path(env))
    for p in [
        Path.home() / ".workbuddy" / "skills",
        Path.home() / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
    ]:
        roots.append(p)
    here = Path(__file__).resolve().parent
    roots.append(here.parent)  # media-automation-lark/
    return [r for r in roots if r.exists()]


def find_skill(name: str) -> Optional[Path]:
    for root in skills_roots():
        cand = root / name
        if (cand / "SKILL.md").exists():
            return cand
    return None


def run(cmd, timeout=60, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")
    except FileNotFoundError:
        return subprocess.CompletedProcess(cmd, 127, "", "command not found")


def _coerce_results(obj):
    """从不同后端的 JSON 结构里尽量抽出 [{title,url,snippet}]。"""
    items = []
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict):
        for k in ("result", "results", "data", "items", "hits"):
            v = obj.get(k)
            if isinstance(v, list):
                items = v
                break
        else:
            if "url" in obj or "link" in obj:
                items = [obj]
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        url = it.get("url") or it.get("link") or it.get("href")
        if not url:
            continue
        out.append({
            "title": it.get("title") or it.get("name") or it.get("text") or url,
            "url": url,
            "snippet": it.get("snippet") or it.get("description") or it.get("content") or "",
        })
    return out


def _parse_anysearch_md(text: str) -> list[dict]:
    """兼容 anysearch CLI 的 Markdown 输出：
    ### 1. 标题
    - **URL**: https://...
    - 摘要文本...
    """
    out = []
    for part in re.split(r"(?m)^###\s+\d+\.\s*", text):
        lines = [ln for ln in part.splitlines() if ln.strip()]
        if not lines:
            continue
        title = lines[0].strip()
        url = None
        snippet = []
        for ln in lines[1:]:
            m = re.search(r"\*\*URL\*\*\s*[:：]\s*(.+)$", ln)
            if m:
                um = re.search(r"https?://\S+", m.group(1))
                if um:
                    url = um.group(0).rstrip(").,")
                continue
            snippet.append(ln.strip())
        if url:
            out.append({"title": title, "url": url, "snippet": " ".join(snippet)[:500]})
    return out


# --------------------------------------------------------------------------
# 后端基类
# --------------------------------------------------------------------------
@dataclass
class Backend:
    name: str
    label: str
    kind: str  # "search" | "fetch"
    scriptable: bool = True          # collector（无头脚本）能否调用
    requires_key: bool = False
    key_env: Optional[str] = None
    git_url: Optional[str] = None
    install_hint: str = ""
    install_method: str = "git"      # git | curl | marketplace

    def is_installed(self) -> bool:  # pragma: no cover - 子类实现
        raise NotImplementedError

    def is_working(self) -> tuple[bool, str]:
        return self.is_installed(), ""

    def search(self, query: str, n: int = 5) -> list[dict]:  # pragma: no cover
        raise NotImplementedError

    def fetch(self, url: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------
# 具体后端
# --------------------------------------------------------------------------
class AnySearchBackend(Backend):
    def __init__(self):
        super().__init__(
            name="anysearch", label="AnySearch（免key也能用）", kind="search",
            requires_key=False, key_env="ANYSEARCH_API_KEY",
            git_url="https://github.com/anysearch-ai/anysearch-skill",
            install_hint="git clone https://github.com/anysearch-ai/anysearch-skill <skills_root>/anysearch",
        )

    def _cli(self):
        d = find_skill("anysearch")
        if d and (d / "scripts" / "anysearch_cli.py").exists():
            return [sys.executable, str(d / "scripts" / "anysearch_cli.py")]
        return None

    def is_installed(self):
        return self._cli() is not None

    def search(self, query, n=5):
        cli = self._cli()
        if not cli:
            return []
        r = run(cli + ["search", query, "--max_results", str(n)], timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            return []
        # 优先按 JSON 解析（部分版本/端点返回 JSON），失败则按 Markdown 解析
        try:
            return _coerce_results(json.loads(r.stdout))
        except Exception:
            return _parse_anysearch_md(r.stdout)

    def fetch(self, url):
        cli = self._cli()
        if not cli:
            return None
        r = run(cli + ["extract", url], timeout=90)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return r.stdout.strip()


class TavilyBackend(Backend):
    def __init__(self):
        super().__init__(
            name="tavily", label="Tavily（需API key）", kind="search",
            requires_key=True, key_env="TAVILY_API_KEY",
            git_url=None, install_method="curl",
            install_hint="curl -fsSL https://cli.tavily.com/install.sh | bash  然后 tvly login",
        )

    def is_installed(self):
        return shutil.which("tvly") is not None

    def is_working(self):
        if not self.is_installed():
            return False, "tvly 未安装"
        r = run(["tvly", "--status"], timeout=30)
        ok = r.returncode == 0 and "unauthenticated" not in r.stdout.lower()
        return ok, ("" if ok else "未登录（需 tvly login 或 TAVILY_API_KEY）")

    def search(self, query, n=5):
        if not self.is_installed():
            return []
        r = run(["tvly", "search", query, "--json", "--max-results", str(n)], timeout=60)
        if r.returncode != 0 or not r.stdout.strip():
            return []
        try:
            obj = json.loads(r.stdout)
        except Exception:
            return []
        if isinstance(obj, dict) and "results" in obj:
            obj = obj["results"]
        return _coerce_results(obj)

    def fetch(self, url):
        if not self.is_installed():
            return None
        r = run(["tvly", "extract", url, "--json"], timeout=90)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        try:
            obj = json.loads(r.stdout)
        except Exception:
            return r.stdout.strip() or None
        if isinstance(obj, dict):
            return obj.get("markdown") or obj.get("content") or obj.get("text")
        return None


class AutocliBackend(Backend):
    def __init__(self):
        super().__init__(
            name="autocli", label="AutoCLI（复用Chrome登录态，read出Markdown）",
            kind="fetch", requires_key=False,
            git_url="https://github.com/nashsu/AutoCLI", install_method="curl",
            install_hint="curl -fsSL https://raw.githubusercontent.com/nashsu/AutoCLI/main/scripts/install.sh | sh （Windows见 github.com/nashsu/AutoCLI）",
        )

    def is_installed(self):
        return shutil.which("autocli") is not None

    def fetch(self, url):
        if not self.is_installed():
            return None
        r = run(["autocli", "read", url, "-f", "markdown"], timeout=90)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        return r.stdout.strip()


class AgentReachBackend(Backend):
    def __init__(self):
        super().__init__(
            name="agent_reach", label="Agent Reach（15平台，交互编排）",
            kind="search", scriptable=False, requires_key=False,
            git_url="https://github.com/Panniantong/Agent-Reach",
            install_hint="git clone https://github.com/Panniantong/Agent-Reach <skills_root>/agent-reach",
        )

    def is_installed(self):
        return shutil.which("agent-reach") is not None or find_skill("agent-reach") is not None

    def search(self, query, n=5):
        # 无头脚本不直接调用；交给 agent 在交互模式编排
        raise NotImplementedError("agent_reach 仅在交互模式由 agent 编排")


class MultiSearchBackend(Backend):
    def __init__(self):
        super().__init__(
            name="multi_search", label="Multi Search Engine（17引擎，免key，依赖WebFetch）",
            kind="search", scriptable=False, requires_key=False,
            git_url=None, install_method="marketplace",
            install_hint="通过 WorkBuddy 技能市场安装 multi-search-engine",
        )

    def is_installed(self):
        return find_skill("multi-search-engine") is not None

    def search(self, query, n=5):
        raise NotImplementedError("multi_search 仅在交互模式由 agent 通过 WebFetch 编排")


# HTTP 兜底（无头脚本也能用，不依赖任何外部 skill）
class HttpFetchBackend(Backend):
    def __init__(self):
        super().__init__(
            name="http", label="HTTP 兜底（requests+BeautifulSoup）",
            kind="fetch", scriptable=True, requires_key=False,
            git_url=None, install_hint="",
        )

    def is_installed(self):
        return REQUESTS_OK

    def fetch(self, url):
        if not REQUESTS_OK:
            return None
        try:
            import common as _c
            if not _c.is_safe_url(url):
                return None
        except Exception:  # noqa: BLE001
            pass
        try:
            resp = requests.get(url, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0 (compatible; media-automation/1.0)"})
            resp.encoding = resp.apparent_encoding or resp.encoding
            html = resp.text
        except Exception:
            return None
        if not BeautifulSoup:
            return html
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "nav", "header", "footer", "aside"]):
            t.extract()
        text = soup.get_text("\n")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n\n".join(lines)


# --------------------------------------------------------------------------
# 注册表与检测
# --------------------------------------------------------------------------
REGISTRY: dict[str, Backend] = {
    b.name: b for b in [
        AnySearchBackend(),
        TavilyBackend(),
        AutocliBackend(),
        AgentReachBackend(),
        MultiSearchBackend(),
        HttpFetchBackend(),
    ]
}

# 无头脚本实际可用的后端（排除仅交互的）
SCRIPTABLE_SEARCH = [REGISTRY["anysearch"], REGISTRY["tavily"]]
SCRIPTABLE_FETCH = [REGISTRY["autocli"], REGISTRY["anysearch"], REGISTRY["tavily"], REGISTRY["http"]]


def detect() -> dict:
    """返回每个后端的检测状态。"""
    status = {}
    for name, b in REGISTRY.items():
        installed = b.is_installed()
        if not installed:
            status[name] = {"installed": False, "working": False, "scriptable": b.scriptable,
                            "label": b.label, "note": b.install_hint or "未安装"}
            continue
        if b.scriptable:
            working, note = b.is_working()
            status[name] = {"installed": True, "working": working, "scriptable": True,
                            "label": b.label, "note": note or "可用"}
        else:
            status[name] = {"installed": True, "working": True, "scriptable": False,
                            "label": b.label, "note": "交互模式可用"}
    return status


def usable_search_backends(only=None) -> list[Backend]:
    out = []
    for b in SCRIPTABLE_SEARCH:
        if only and b.name not in only:
            continue
        if b.is_installed() and b.is_working()[0]:
            out.append(b)
    return out


def usable_fetch_backends(only=None) -> list[Backend]:
    out = []
    for b in SCRIPTABLE_FETCH:
        if only and b.name not in only:
            continue
        if b.is_installed() and b.is_working()[0]:
            out.append(b)
    return out


def fetch_markdown(url: str, only=None) -> Optional[str]:
    """按优先级用可用后端抓取 URL 的 Markdown 正文。"""
    for b in usable_fetch_backends(only):
        try:
            md = b.fetch(url)
            if md and md.strip():
                return md
        except Exception:
            continue
    return None


def search_all(query: str, n: int = 5, only=None) -> list[dict]:
    """跨所有可用搜索后端收集候选 URL（已去重）。"""
    seen, results = set(), []
    for b in usable_search_backends(only):
        try:
            for item in b.search(query, n):
                u = item["url"]
                if u in seen:
                    continue
                seen.add(u)
                item = dict(item)
                item["backend"] = b.name
                results.append(item)
        except Exception:
            continue
    return results


if __name__ == "__main__":
    print(json.dumps(detect(), ensure_ascii=False, indent=2))
