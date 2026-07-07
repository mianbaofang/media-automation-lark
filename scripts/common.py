#!/usr/bin/env python3
"""media-automation-lark 公共模块：配置、密钥、LLM、lark-cli 封装、HTTP。

所有脚本共享此模块，避免重复代码。脆弱操作（API 鉴权、重试、字段转换）集中在此，
业务脚本不要重复实现，也不要自行调整重试间隔。
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import time
from typing import Any, Optional

logger = logging.getLogger("media-automation")

# ---- 重试参数（集中管理，业务脚本不要改）----
HTTP_RETRIES = 3
HTTP_BASE_DELAY = 2.0
LARK_RETRIES = 3
LARK_BASE_DELAY = 2.0
LARK_DATA_FLAG = "--data"  # lark-cli api 的数据标志；如实际不同，只改此处

RETRYABLE_HTTP = {429, 500, 502, 503, 504}


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def load_config(path: Optional[str]) -> dict:
    """加载 config.json；路径为空时按 ./config.json、<skill>/config.json 依次查找。"""
    candidates: list[str] = []
    if path:
        candidates.append(path)
    candidates.append(os.path.join(os.getcwd(), "config.json"))
    here = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(os.path.dirname(here), "config.json"))
    for c in candidates:
        if c and os.path.isfile(c):
            with open(c, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(
        "未找到 config.json。请先复制 config.json.example 为 config.json 并填写，"
        "或用 --config 指定路径。查找过：" + ", ".join(candidates)
    )


def require_secret(env_name: str, config_value: Optional[str] = None) -> str:
    """从环境变量或 @env: 占位符取密钥；缺失则抛清晰错误。绝不返回硬编码明文。"""
    val = os.environ.get(env_name)
    if val:
        return val
    if isinstance(config_value, str) and config_value.startswith("@env:"):
        return os.environ.get(config_value[5:], "") or ""
    if config_value and not config_value.startswith("@env:"):
        # 允许本地非敏感配置直接写值；api_key 类强烈建议走 @env:
        return config_value
    raise RuntimeError(
        f"缺少密钥 {env_name}。请设置环境变量，或在 config.json 中写 \"@env:{env_name}\"。"
    )


def extract_json(text: str) -> dict:
    """从可能含日志的 stdout 中提取第一个 JSON 对象。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("无法从 lark-cli 输出解析 JSON")


def run_lark(
    args: list[str],
    data: Any = None,
    config: Optional[dict] = None,
    dry_run: bool = False,
    yes: bool = False,
) -> dict:
    """执行 lark-cli 命令，返回解析后的输出信封（含 ok 字段）。"""
    cfg = (config or {}).get("feishu", {})
    cli = cfg.get("lark_cli_path") or "lark-cli"
    cmd = [cli, *args]
    if yes and "--yes" not in cmd:
        cmd.append("--yes")
    if data is not None:
        payload_str = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        cmd += [cfg.get("data_flag") or LARK_DATA_FLAG, payload_str]

    if dry_run:
        logger.info("[DRY-RUN] 将执行: %s", " ".join(shlex.quote(c) for c in cmd))
        return {"ok": True, "data": {"dry_run": True}, "meta": {"cmd": cmd}}

    last_err: Optional[Exception] = None
    for attempt in range(1, LARK_RETRIES + 1):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            out = (proc.stdout or "").strip()
            if proc.returncode != 0:
                last_err = RuntimeError(f"lark-cli 退出码 {proc.returncode}: {proc.stderr.strip()}")
            else:
                envelope = extract_json(out)
                if envelope.get("ok") is True:
                    return envelope
                last_err = RuntimeError(f"lark-cli ok=false: {out[:500]}")
        except Exception as e:  # noqa: BLE001
            last_err = e
        if attempt < LARK_RETRIES:
            time.sleep(LARK_BASE_DELAY * attempt)
    raise RuntimeError(f"lark-cli 调用失败（已重试 {LARK_RETRIES} 次）: {last_err}")


def write_bitable_records(
    app_token: str,
    table_id: str,
    records: list[dict],
    config: dict,
    dry_run: bool = False,
    yes: bool = False,
) -> dict:
    """批量写入多维表格。records 为 [{fields:{...}}, ...]。飞书单次最多 500 行。"""
    if not records:
        logger.info("无记录可写，跳过。")
        return {"ok": True, "data": {"written": 0}}
    path = f"/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create"
    CHUNK = 500
    written = 0
    for i in range(0, len(records), CHUNK):
        chunk = records[i : i + CHUNK]
        payload = {"records": chunk}
        res = run_lark(["api", "POST", path], data=payload, config=config, dry_run=dry_run, yes=yes)
        if not dry_run and not res.get("ok"):
            raise RuntimeError(f"写入分片 {i} 失败: {res}")
        written += len(chunk)
    return {"ok": True, "data": {"written": written}}


def create_doc(title: str, markdown: str, config: dict, dry_run: bool = False) -> dict:
    """创建飞书云文档，返回含 url/document_id 的信封。"""
    return run_lark(
        ["docs", "+create", "--title", title, "--markdown", markdown],
        config=config,
        dry_run=dry_run,
    )


def send_im(chat_id: str, text: str, config: dict, as_bot: bool = True, dry_run: bool = False) -> dict:
    args = ["im", "+messages-send", "--chat-id", chat_id, "--text", text]
    if as_bot:
        args += ["--as", "bot"]
    return run_lark(args, config=config, dry_run=dry_run)


def llm_chat(
    system: str,
    user: str,
    config: dict,
    expect_json: bool = False,
    vision_b64: Optional[str] = None,
) -> Any:
    """调用 OpenAI 兼容 Chat Completions。返回解析后的 JSON 或文本。"""
    import requests  # 延迟导入，避免无网络环境也强制依赖

    llm = config.get("llm", {})
    api_key = require_secret(llm.get("env_key") or "LARK_LLM_API_KEY", llm.get("api_key"))
    api_base = llm.get("api_base") or "https://api.openai.com/v1"
    model = vision_b64 and llm.get("vision_model") or llm.get("model") or "gpt-4o-mini"
    timeout = llm.get("timeout") or 60

    user_content: Any = user
    if vision_b64:
        user_content = [
            {"type": "text", "text": user},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{vision_b64}"}},
        ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    last_err: Optional[Exception] = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            r = requests.post(f"{api_base}/chat/completions", json=payload, headers=headers, timeout=timeout)
            if r.status_code in RETRYABLE_HTTP:
                last_err = RuntimeError(f"HTTP {r.status_code}")
            elif r.ok:
                content = r.json()["choices"][0]["message"]["content"]
                return json.loads(content) if expect_json else content
            else:
                if r.status_code in (401, 403):
                    raise RuntimeError(f"LLM_AUTH {r.status_code}: {r.text[:200]}")
                raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:  # noqa: BLE001
            last_err = e
            if "LLM_AUTH" in str(e):
                break  # 鉴权失败不重试，立即降级
        if attempt < HTTP_RETRIES:
            time.sleep(HTTP_BASE_DELAY * attempt)
    raise RuntimeError(f"LLM 调用失败（已重试 {HTTP_RETRIES} 次）: {last_err}")


def http_get(url: str, headers: Optional[dict] = None, timeout: int = 30) -> str:
    """带重试的 GET，返回文本。"""
    import requests

    last_err: Optional[Exception] = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            r = requests.get(url, headers=headers or {}, timeout=timeout)
            if r.status_code in RETRYABLE_HTTP:
                last_err = RuntimeError(f"HTTP {r.status_code}")
            elif r.ok:
                return r.text
            else:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            last_err = e
        if attempt < HTTP_RETRIES:
            time.sleep(HTTP_BASE_DELAY * attempt)
    raise RuntimeError(f"HTTP GET 失败（已重试 {HTTP_RETRIES} 次）: {last_err}")


def ensure_output_dir(config: dict) -> str:
    d = (config.get("paths", {}) or {}).get("output_dir") or os.path.join(os.getcwd(), "output")
    os.makedirs(d, exist_ok=True)
    return d


# ---- 文本润色（renhua / 人话 · 去 AI 味）----
# renhua 是基于提示词的 Agent 技能（非 CLI），只能由 LLM 套用其规则改写文字。
# 安装时从 https://github.com/Pluviobyte/rnskill 把 skills/renhua 拉到用户 skills 目录；
# 此处运行时读取其 SKILL.md 作为改写规则（单一事实源），缺失则用内置精简兜底。

def find_renhua_skill() -> Optional["Path"]:
    """定位已安装的 renhua/SKILL.md；找不到返回 None。"""
    from pathlib import Path

    here = Path(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        here.parent / "renhua" / "SKILL.md",
        Path.home() / ".workbuddy" / "skills" / "renhua" / "SKILL.md",
        Path.home() / ".agents" / "skills" / "renhua" / "SKILL.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


_RENHUA_FALLBACK = (
    "请用自然、直接的中文重写，去掉 AI 腔："
    "1) 避免「不是A而是B」「不只是A更是B」「与其A不如B」等二元对比壳；"
    "2) 避免「真正/其实/本质上/关键在于/更重要的是/说白了」等伪洞察词；"
    "3) 避免冒号讲义腔（如「我的结论是：」「重点是：」）；"
    "4) 用具体动词和已完成时态，保留事实、数字、专名与作者判断；"
    "5) 不要加 emoji、话题标签或编号列表（除非要求）。只输出改写后的文本。"
)


def load_polish_rules() -> str:
    """读取 renhua SKILL.md 正文作改写规则；缺失则用内置兜底。"""
    p = find_renhua_skill()
    if p:
        try:
            txt = p.read_text(encoding="utf-8")
            if txt.startswith("---"):
                end = txt.find("---", 3)
                if end != -1:
                    txt = txt[end + 3:]
            return txt.strip()
        except Exception:  # noqa: BLE001
            pass
    return _RENHUA_FALLBACK


def is_polish_enabled(config: dict) -> bool:
    return bool((config.get("text", {}) or {}).get("polish", False))


def polish_text(text: str, config: dict, system: Optional[str] = None, max_chars: int = 4000) -> str:
    """用 renhua 规则润色文本。未启用 / 无 LLM key 时原样返回（优雅降级）。

    text 应是本 Skill 自己产出的文字（摘要、标题、索引、通知），而非抓取的原文。
    """
    if not text or not is_polish_enabled(config):
        return text
    rules = system or load_polish_rules()
    sys_prompt = (
        "你是中文去 AI 味改写编辑。根据用户给出的规则修改文本，"
        "保留事实、数字、专名与作者判断；只输出改写后的文本，不要任何前言或诊断。\n\n"
        "【改写规则】\n" + rules
    )
    chunk = text if len(text) <= max_chars else text[:max_chars] + "\n…（原文较长，已截断）"
    try:
        out = llm_chat(sys_prompt, chunk, config)
    except Exception as e:  # noqa: BLE001
        logger.debug("polish 跳过（LLM 不可用）：%s", e)
        return text
    return out.strip() if out else text


# ---- 安全：URL 校验（SSRF 防护）----
import ipaddress
import urllib.parse as _urlparse

_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "metadata", "fd00:ec2::254"}


def is_safe_url(url: str, allow_private: bool = False) -> bool:
    """拦截非 http(s)、loopback、link-local、cloud metadata、私网（除非 allow_private）。"""
    try:
        p = _urlparse.urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if p.scheme not in ("http", "https"):
        return False
    host = (p.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS or host in ("localhost",):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            return False
        if not allow_private and (ip.is_private or ip.is_reserved):
            return False
    except ValueError:
        pass  # 域名放行（个人用，不做 DNS 解析防 rebinding）
    return True


# ---- 配置校验 ----
def validate_config(config: dict) -> list[str]:
    """返回告警列表；空列表表示 OK。轻量校验，不阻断 dry-run。"""
    errs: list[str] = []
    if not isinstance(config, dict):
        return ["config 顶层不是 JSON 对象"]
    llm = config.get("llm", {})
    if llm and not (llm.get("api_key") or llm.get("env_key")):
        errs.append("llm 段缺少 api_key/env_key（润色与提取将降级）")
    feishu = config.get("feishu", {})
    if feishu and feishu.get("app_token") and not (feishu.get("table_id") or feishu.get("archive_table_id")):
        errs.append("feishu.app_token 已配但缺 table_id/archive_table_id（内容归档将跳过）")
    return errs


# ---- 归档去重（幂等）----
def seen_path(config: dict) -> str:
    d = (config.get("paths", {}) or {}).get("output_dir") or os.path.join(os.getcwd(), "output")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "seen.jsonl")


def load_seen(config: dict) -> set[str]:
    p = seen_path(config)
    s: set[str] = set()
    if os.path.isfile(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if ln:
                        s.add(ln)
        except Exception:  # noqa: BLE001
            pass
    return s


def mark_seen(config: dict, key: str) -> None:
    try:
        with open(seen_path(config), "a", encoding="utf-8") as f:
            f.write(dedup_key(key) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.debug("mark_seen 失败：%s", e)


def dedup_key(url: str) -> str:
    return (url or "").strip().lower()
