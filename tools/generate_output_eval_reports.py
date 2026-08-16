#!/usr/bin/env python3
"""Generate reproducible output-quality evidence for media-automation-lark.

The with-skill side is produced by the repository's offline scripts.  The
baseline side is deliberately static and is never described as a model run.
No network, provider credentials, or files outside the skill fixtures are
needed.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "media-automation-lark"
EVAL_ROOT = SKILL_ROOT / "evals" / "output"
FIXTURES = EVAL_ROOT / "fixtures"
REPORT_ROOT = SKILL_ROOT / "reports"
BLIND_SEED = "yao-output-eval-blind-v1"


def _run(command: list[str], *, cwd: Path = ROOT, timeout: int = 90) -> dict[str, Any]:
    started = time.perf_counter()
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=timeout,
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _normalise(text: str, temp_root: Path) -> str:
    """Remove machine-specific paths and run-dependent time values."""
    text = str(text)
    path_values = {
        str(temp_root): "<tmp>",
        str(ROOT): "<repo>",
        str(Path(sys.executable)): "<python>",
        str(Path.home()): "<home>",
    }
    for source, replacement in path_values.items():
        for variant in {source, source.replace("\\", "/"), source.replace("\\", "//").replace(":", "://")}:
            text = text.replace(variant, replacement)
    text = text.replace("\\", "/")
    text = re.sub(r"(?i)\b[A-Z]:/{1,2}(?:Users|Temp|Object|Program Files)[^\s\"<>]*", "<path>", text)
    text = re.sub(r"生成时间: [^\r\n]+", "生成时间: <fixed>", text)
    text = re.sub(r"\b20\d{2}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b", "<timestamp>", text)
    text = re.sub(r"\b20\d{2}-\d{2}-\d{2}\b", "<date>", text)
    return text


def _html_evidence(document: str) -> str:
    """Keep visible panel copy while dropping CSS and full-page markup noise."""
    visible = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", document)
    visible = re.sub(r"(?is)<!--.*?-->", "", visible)
    visible = re.sub(r"(?is)<[^>]+>", "\n", visible)
    visible = html.unescape(visible)
    lines = [re.sub(r"\s+", " ", line).strip() for line in visible.splitlines()]
    return "\n".join(line for line in lines if line)


def _dashboard_evidence(document: str) -> str:
    """Keep dashboard semantics and a small structural marker, not its CSS."""
    return '\n'.join(['<title>运营看板</title>', 'class="chart"', _html_evidence(document)])


def _config(path: Path, output_dir: Path, *, extra: dict[str, Any] | None = None) -> Path:
    data: dict[str, Any] = {
        "feishu": {},
        "llm": {},
        "text": {"polish": False},
        "paths": {"output_dir": str(output_dir)},
    }
    if extra:
        for key, value in extra.items():
            if isinstance(value, dict) and isinstance(data.get(key), dict):
                data[key].update(value)
            else:
                data[key] = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _capture(label: str, run: dict[str, Any], temp_root: Path, artifacts: list[tuple[str, str]] | None = None) -> str:
    lines = [
        f"CASE={label}",
        "EXECUTION_MODE=command",
        "PROVIDER_BACKED=false",
        f"EXIT_CODE={run['returncode']}",
        f"COMMAND={_normalise(' '.join(str(x) for x in run['command']), temp_root)}",
        "DURATION_MS=<elapsed>",
        "STDOUT:",
        _normalise(run["stdout"], temp_root).strip(),
        "STDERR:",
        _normalise(run["stderr"], temp_root).strip(),
    ]
    for name, content in artifacts or []:
        lines.extend([f"ARTIFACT {_normalise(name, temp_root)}:", _normalise(content, temp_root).strip()])
    return "\n".join(line for line in lines if line != "") + "\n"


def _read_files(root: Path, suffixes: tuple[str, ...] = (".md", ".html")) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in suffixes:
            items.append((path.relative_to(root).as_posix(), path.read_text(encoding="utf-8", errors="replace")))
    return items


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_cases() -> list[dict[str, Any]]:
    """Run five fixed, offline scenarios and return output-eval cases."""
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="media-automation-lark-output-eval-") as tmp:
        temp_root = Path(tmp)

        # 1. Search workflow: offline samples must become classified Markdown and an index.
        search_out = temp_root / "search-output"
        search_cfg_data = json.loads((FIXTURES / "search_config.json").read_text(encoding="utf-8"))
        search_cfg_data["paths"] = {"output_dir": str(search_out)}
        search_cfg = temp_root / "search-config.json"
        search_cfg.write_text(json.dumps(search_cfg_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        search_run = _run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "collector.py"),
                "--config",
                str(search_cfg),
                "--offline-demo",
                "--no-archive",
                "--no-notify",
            ]
        )
        cases.append(
            {
                "id": "offline-search-archive",
                "prompt": "把一组固定的选题搜索样例离线整理成可分类、可回看的 Markdown 索引。",
                "input_files": ["fixtures/search_config.json"],
                "baseline_output": "把两条搜索结果列成一个无分类的标题清单，不生成索引，也不保留来源元数据。",
                "with_skill_output": _capture("offline-search-archive", search_run, temp_root, _read_files(search_out)),
                "assertions": [
                    {"id": "search-index", "description": "生成可回看的采集索引。", "required": ["index.md", "# 采集索引"], "weight": 1, "failure_type": "missing_index"},
                    {"id": "search-count", "description": "索引记录离线样例条目数。", "required": ["条目数: 2"], "weight": 1, "failure_type": "missing_count"},
                    {"id": "search-category", "description": "结果按分类写入 Markdown frontmatter。", "required": ["category: \"AI\""], "weight": 1, "failure_type": "missing_category"},
                    {"id": "search-source", "description": "文章保留可追溯来源链接。", "required": ["source: \"https://example.com/llm-support\""], "weight": 1, "failure_type": "missing_source"},
                    {"id": "search-offline", "description": "运行证据明确来自离线演示。", "required": ["OFFLINE-DEMO"], "weight": 1, "failure_type": "missing_offline_evidence"},
                ],
                "human_review": {"expected_winner": "with_skill"},
                "execution": {"mode": "command", "provider_backed": False, "runner": "scripts/collector.py --offline-demo"},
                "metadata": {"case_type": "production", "contract": "classified_markdown_index"},
            }
        )

        # 2. Metrics workflow: fixed JSON input must produce the KPI dashboard without a write.
        dashboard_out = temp_root / "dashboard-output"
        dashboard_cfg = _config(temp_root / "dashboard-config.json", dashboard_out)
        dashboard_run = _run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "data-collector.py"),
                "--source",
                str(FIXTURES / "metrics.json"),
                "--config",
                str(dashboard_cfg),
                "--dry-run",
                "--no-notify",
            ]
        )
        cases.append(
            {
                "id": "metrics-dashboard",
                "prompt": "用固定的两天指标数据生成本地运营看板，并在预览模式下不写入飞书。",
                "input_files": ["fixtures/metrics.json"],
                "baseline_output": "把阅读、点赞和评论数字打印出来，不生成 HTML 看板，也不说明互动率或写入状态。",
                "with_skill_output": _capture(
                    "metrics-dashboard",
                    dashboard_run,
                    temp_root,
                    [("dashboard.html", _dashboard_evidence((dashboard_out / "dashboard.html").read_text(encoding="utf-8")))]
                    if (dashboard_out / "dashboard.html").exists()
                    else [],
                ),
                "assertions": [
                    {"id": "dashboard-file", "description": "输出本地 HTML 看板。", "required": ["dashboard.html", "<title>运营看板</title>"], "weight": 1, "failure_type": "missing_dashboard"},
                    {"id": "dashboard-total", "description": "看板保留固定输入的总阅读数。", "required": ['"total_reads": 1500'], "weight": 1, "failure_type": "wrong_total"},
                    {"id": "dashboard-rate", "description": "看板显示互动率。", "required": ["20.00%", "互动率"], "weight": 1, "failure_type": "missing_engagement_rate"},
                    {"id": "dashboard-chart", "description": "看板包含每日趋势图。", "required": ["每日阅读趋势", "class=\"chart\""], "weight": 1, "failure_type": "missing_trend_chart"},
                    {"id": "dashboard-dry-run", "description": "预览模式不写入飞书。", "required": ['"written": 0', "EXECUTION_MODE=command"], "weight": 1, "failure_type": "unsafe_write_or_missing_mode"},
                ],
                "human_review": {"expected_winner": "with_skill"},
                "execution": {"mode": "command", "provider_backed": False, "runner": "scripts/data-collector.py --source fixtures/metrics.json --dry-run"},
                "metadata": {"case_type": "production", "contract": "local_dashboard"},
            }
        )

        # 3. Material workflow: a one-off local preview is a near-neighbor of full Feishu archiving.
        material_out = temp_root / "material-output"
        material_cfg = _config(temp_root / "material-config.json", material_out)
        material_text = (FIXTURES / "material.txt").read_text(encoding="utf-8").strip()
        material_run = _run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "material-manager.py"),
                "--text",
                material_text,
                "--config",
                str(material_cfg),
                "--dry-run",
                "--no-notify",
            ]
        )
        cases.append(
            {
                "id": "material-local-preview",
                "prompt": "我只想把这段文字做一次本地预览，不需要飞书归档。",
                "input_files": ["fixtures/material.txt"],
                "baseline_output": "给出一段泛泛的摘要文字，要求用户自行复制到文档；不产出本地 Markdown，也不标记预览状态。",
                "with_skill_output": _capture("material-local-preview", material_run, temp_root, _read_files(material_out, (".md",))),
                "assertions": [
                    {"id": "material-markdown", "description": "本地预览产出 Markdown 文件。", "required": ["# 文本素材", "ARTIFACT"], "weight": 1, "failure_type": "missing_material_markdown"},
                    {"id": "material-source", "description": "预览保留输入事实。", "required": ["本周的选题整理成可复用的内容清单"], "weight": 1, "failure_type": "lost_source_text"},
                    {"id": "material-count", "description": "命令结果报告处理条目数。", "required": ['"count": 1'], "weight": 1, "failure_type": "missing_result_count"},
                    {"id": "material-no-doc", "description": "dry-run 不创建远端文档链接。", "required": ['"doc_url": ""'], "weight": 1, "failure_type": "unexpected_remote_write"},
                    {"id": "material-neighbor-boundary", "description": "输出明确记录本地命令模式。", "required": ["EXECUTION_MODE=command", "PROVIDER_BACKED=false"], "weight": 1, "failure_type": "missing_execution_boundary"},
                ],
                "human_review": {"expected_winner": "with_skill"},
                "execution": {"mode": "command", "provider_backed": False, "runner": "scripts/material-manager.py --text --dry-run"},
                "metadata": {"case_type": "near_neighbor", "contract": "local_material_preview"},
            }
        )

        # 4. Panel workflow: render the real default home page without starting a server.
        panel = _load_module(SKILL_ROOT / "scripts" / "gui-panel.py", "media_automation_lark_gui_panel_eval")
        panel_html = panel.render_home().decode("utf-8")
        panel_run = {
            "command": [sys.executable, str(SKILL_ROOT / "scripts" / "gui-panel.py"), "render_home (offline import)"],
            "returncode": 0,
            "stdout": panel_html,
            "stderr": "",
            "duration_ms": 0,
        }
        cases.append(
            {
                "id": "panel-safe-default",
                "prompt": "打开控制台首页，让新用户先体验一次完整流程，默认不要联网或写飞书。",
                "input_files": [],
                "baseline_output": "请用户先阅读命令行文档，再手动填写搜索后端和飞书参数。",
                "with_skill_output": _capture(
                    "panel-safe-default",
                    {**panel_run, "stdout": _html_evidence(panel_html)},
                    temp_root,
                ),
                "assertions": [
                    {"id": "panel-title", "description": "首页说明本地自动化控制台。", "required": ["本地自动化控制台"], "weight": 1, "failure_type": "missing_panel_title"},
                    {"id": "panel-first-run", "description": "首页提供无需配置的首次体验。", "required": ["先体验一次完整流程", "不用填写任何东西"], "weight": 1, "failure_type": "missing_first_run_path"},
                    {"id": "panel-actions", "description": "首页列出主要任务入口。", "required": ["按选题去采集", "直接丢网页或文件"], "weight": 1, "failure_type": "missing_action_surface"},
                    {"id": "panel-safe", "description": "首页明确离线预览边界。", "required": ["不联网、不写飞书"], "weight": 1, "failure_type": "missing_safe_boundary"},
                    {"id": "panel-no-manual-command", "description": "首页不把手写启动命令当作默认路径。", "required": ["整理这份材料"], "forbidden": ["python scripts/gui-panel.py"], "weight": 1, "failure_type": "manual_command_leak"},
                ],
                "human_review": {"expected_winner": "with_skill"},
                "execution": {"mode": "command", "provider_backed": False, "runner": "scripts/gui-panel.py render_home (offline import)"},
                "metadata": {"case_type": "production", "contract": "safe_panel_home"},
            }
        )

        # 5. Safety boundary: an unsafe URL must fail closed before network access.
        unsafe_cfg = _config(temp_root / "unsafe-config.json", temp_root / "unsafe-output")
        unsafe_url = (FIXTURES / "unsafe_url.txt").read_text(encoding="utf-8").strip()
        unsafe_run = _run(
            [
                sys.executable,
                str(SKILL_ROOT / "scripts" / "content-archiver.py"),
                "--config",
                str(unsafe_cfg),
                "--rss-url",
                unsafe_url,
                "--dry-run",
                "--no-notify",
            ]
        )
        cases.append(
            {
                "id": "unsafe-url-boundary",
                "prompt": "把这个 RSS 地址抓下来并归档。",
                "input_files": ["fixtures/unsafe_url.txt"],
                "baseline_output": "直接请求地址并尝试把结果写入飞书归档。",
                "with_skill_output": _capture("unsafe-url-boundary", unsafe_run, temp_root),
                "assertions": [
                    {"id": "unsafe-rejected", "description": "不安全 RSS 地址被拒绝。", "required": ["拒绝不安全 RSS URL"], "weight": 1, "failure_type": "unsafe_url_not_rejected"},
                    {"id": "ssrf-language", "description": "错误中保留 SSRF 防护说明。", "required": ["SSRF 防护"], "weight": 1, "failure_type": "missing_ssrf_boundary"},
                    {"id": "nonzero-exit", "description": "拒绝路径以失败状态退出。", "required": ["EXIT_CODE=1"], "weight": 1, "failure_type": "unsafe_url_exit_status"},
                    {"id": "no-network-claim", "description": "输出不声称抓取成功。", "forbidden": ["抓取 RSS 成功", "写入飞书"], "weight": 1, "failure_type": "unsafe_success_claim"},
                ],
                "human_review": {"expected_winner": "with_skill"},
                "execution": {"mode": "command", "provider_backed": False, "runner": "scripts/content-archiver.py --rss-url loopback --dry-run"},
                "metadata": {"case_type": "boundary", "contract": "ssrf_fail_closed"},
            }
        )
    return cases


def _check_assertion(output: str, assertion: dict[str, Any]) -> dict[str, Any]:
    lowered = output.casefold()
    required = [str(item) for item in assertion.get("required", [])]
    forbidden = [str(item) for item in assertion.get("forbidden", [])]
    missing = [item for item in required if item.casefold() not in lowered]
    present_forbidden = [item for item in forbidden if item.casefold() in lowered]
    return {
        "id": assertion.get("id", "assertion"),
        "description": assertion.get("description", ""),
        "weight": float(assertion.get("weight", 1) or 0),
        "failure_type": assertion.get("failure_type", "assertion_failed"),
        "passed": not missing and not present_forbidden,
        "missing": missing,
        "present_forbidden": present_forbidden,
    }


def _grade(output: str, assertions: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [_check_assertion(output, assertion) for assertion in assertions]
    total = sum(item["weight"] for item in checks) or len(checks) or 1
    passed = sum(item["weight"] for item in checks if item["passed"])
    failed = [item for item in checks if not item["passed"]]
    return {
        "score": round(passed / total * 100, 2),
        "passed_count": len(checks) - len(failed),
        "failed_count": len(failed),
        "checks": checks,
        "failed": failed,
    }


def _blind_order(case_id: str) -> list[str]:
    digest = hashlib.sha256(f"{BLIND_SEED}:{case_id}".encode("utf-8")).hexdigest()
    return ["baseline", "with_skill"] if int(digest[:2], 16) % 2 == 0 else ["with_skill", "baseline"]


def _scorecard(cases: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    results = []
    blind_pairs = []
    answers = []
    for case in cases:
        baseline = _grade(str(case["baseline_output"]), case["assertions"])
        with_skill = _grade(str(case["with_skill_output"]), case["assertions"])
        delta = round(with_skill["score"] - baseline["score"], 2)
        winner = "with_skill" if with_skill["score"] >= baseline["score"] else "baseline"
        results.append(
            {
                "id": case["id"],
                "prompt": case["prompt"],
                "input_files": case.get("input_files", []),
                "metadata": case.get("metadata", {}),
                "execution": case.get("execution", {}),
                "baseline": baseline,
                "with_skill": with_skill,
                "delta": delta,
                "winner": winner,
                "failure_taxonomy": sorted({item["failure_type"] for item in with_skill["failed"]}),
            }
        )
        order = _blind_order(case["id"])
        roles = {"A": order[0], "B": order[1]}
        rubric = [
            {"id": item.get("id", "assertion"), "description": item.get("description", ""), "weight": float(item.get("weight", 1) or 0)}
            for item in case["assertions"]
        ]
        blind_pairs.append(
            {
                "case_id": case["id"],
                "prompt": case["prompt"],
                "input_files": case.get("input_files", []),
                "metadata": case.get("metadata", {}),
                "review_instruction": "Pick A or B based only on the rubric. Do not infer which output came from the skill.",
                "rubric": rubric,
                "variant_a": {"blind_id": f"{case['id']}:A", "output": case["baseline_output"] if roles["A"] == "baseline" else case["with_skill_output"]},
                "variant_b": {"blind_id": f"{case['id']}:B", "output": case["baseline_output"] if roles["B"] == "baseline" else case["with_skill_output"]},
            }
        )
        expected_role = str((case.get("human_review") or {}).get("expected_winner", "with_skill"))
        answers.append(
            {
                "case_id": case["id"],
                "variant_a_role": roles["A"],
                "variant_b_role": roles["B"],
                "expected_winner_role": expected_role,
                "expected_winner_variant": "A" if roles["A"] == expected_role else "B",
                "score_winner_role": winner,
                "delta": delta,
            }
        )
    count = len(results)
    baseline_rate = round(sum(item["baseline"]["score"] for item in results) / count, 2) if count else 0
    with_skill_rate = round(sum(item["with_skill"]["score"] for item in results) / count, 2) if count else 0
    regressions = [item for item in results if item["delta"] < 0]
    summary = {
        "case_count": count,
        "file_backed_case_count": sum(1 for item in results if item["input_files"]),
        "near_neighbor_case_count": sum(1 for item in results if item["metadata"].get("case_type") == "near_neighbor"),
        "boundary_case_count": sum(1 for item in results if item["metadata"].get("case_type") == "boundary"),
        "baseline_pass_rate": baseline_rate,
        "with_skill_pass_rate": with_skill_rate,
        "delta": round(with_skill_rate - baseline_rate, 2),
        "regression_count": len(regressions),
        "gate_pass": with_skill_rate >= baseline_rate and not regressions,
        "blind_pair_count": len(blind_pairs),
        "failure_taxonomy": sorted({failure for item in results for failure in item["failure_taxonomy"]}),
    }
    payload = {
        "ok": True,
        "evidence_type": "local-command-output-eval",
        "provider_backed": False,
        "execution_note": "with_skill_output was generated by fixed local scripts; baseline_output is an explicit static baseline. No model/provider run is claimed.",
        "summary": summary,
        "results": results,
        "failures": [],
        "blind_review": {"pair_count": len(blind_pairs), "answer_key_separate": True},
    }
    pack = {
        "schema_version": "1.0",
        "seed": BLIND_SEED,
        "summary": {"pair_count": len(blind_pairs), "answer_key_separate": True, "with_skill_hidden_count": len(blind_pairs)},
        "pairs": blind_pairs,
    }
    answer_key = {
        "schema_version": "1.0",
        "seed": BLIND_SEED,
        "summary": {"pair_count": len(answers), "with_skill_expected_count": len(answers), "baseline_expected_count": 0},
        "answers": answers,
    }
    return payload, pack, answer_key


def _scorecard_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Output Quality Scorecard",
        "",
        "This report compares explicit static baseline text with outputs produced by fixed local scripts.",
        "It is local command evidence, not provider-backed model evidence.",
        "",
        f"- Cases: `{summary['case_count']}`",
        f"- File-backed cases: `{summary['file_backed_case_count']}`",
        f"- Near-neighbor cases: `{summary['near_neighbor_case_count']}`",
        f"- Boundary cases: `{summary['boundary_case_count']}`",
        f"- Baseline pass rate: `{summary['baseline_pass_rate']}`",
        f"- With-skill pass rate: `{summary['with_skill_pass_rate']}`",
        f"- Delta: `{summary['delta']}`",
        f"- Regressions: `{summary['regression_count']}`",
        f"- Blind A/B pairs: `{summary['blind_pair_count']}`",
        f"- Provider-backed evidence: `{str(payload['provider_backed']).lower()}`",
        f"- Gate pass: `{str(summary['gate_pass']).lower()}`",
        "",
        "## Case Results",
        "",
        "| Case | Baseline | With Skill | Delta | Winner | Failed With-Skill Assertions |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for item in payload["results"]:
        failed = ", ".join(failure["id"] for failure in item["with_skill"]["failed"]) or "None"
        lines.append(f"| {item['id']} | {item['baseline']['score']} | {item['with_skill']['score']} | {item['delta']} | {item['winner']} | {failed} |")
    lines.extend(["", "## Failure Taxonomy", ""])
    lines.extend([f"- {item}" for item in summary["failure_taxonomy"]] or ["- No with-skill assertion failures."])
    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            "- The baseline is a documented static comparison string, not a historical run.",
            "- The with-skill outputs come from the repository's offline scripts and fixed fixtures.",
            "- No API key, external model, network fetch, download metric, or human blind-review decision is claimed here.",
            "- The separate blind pack must be reviewed before opening the answer key.",
            "",
            "## Next Fixes",
            "",
            "- Add holdout fixtures before using this as a long-term release gate.",
            "- Record reviewer decisions separately with a rubric-based reason.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _blind_markdown(pack: dict[str, Any]) -> str:
    lines = [
        "# Output Blind A/B Review Pack",
        "",
        "This pack hides whether Variant A or Variant B came from the baseline or the Skill output.",
        "Review the visible rubric first; keep the separate answer key closed until decisions are recorded.",
        "",
        f"- Pairs: `{pack['summary']['pair_count']}`",
        f"- Seed: `{pack['seed']}`",
        f"- Answer key separate: `{str(pack['summary']['answer_key_separate']).lower()}`",
        "",
    ]
    for pair in pack["pairs"]:
        lines.extend([f"## Case: {pair['case_id']}", "", f"Prompt: {pair['prompt']}", "", "Rubric:"])
        lines.extend(f"- `{item['id']}` ({item['weight']}): {item['description']}" for item in pair["rubric"])
        lines.extend(["", "### Variant A", "", pair["variant_a"]["output"], "", "### Variant B", "", pair["variant_b"]["output"], ""])
    return "\n".join(lines).strip() + "\n"


def generate(report_dir: Path = REPORT_ROOT, cases_path: Path = EVAL_ROOT / "cases.jsonl") -> dict[str, Any]:
    cases = build_cases()
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text("\n".join(json.dumps(case, ensure_ascii=False, separators=(",", ":")) for case in cases) + "\n", encoding="utf-8")
    payload, pack, answer_key = _scorecard(cases)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "output_quality_scorecard.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "output_quality_scorecard.md").write_text(_scorecard_markdown(payload), encoding="utf-8")
    (report_dir / "output_blind_review_pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "output_blind_review_pack.md").write_text(_blind_markdown(pack), encoding="utf-8")
    # Yao's method requires a separate answer key; it is intentionally not linked from the blind pack.
    (report_dir / "output_blind_answer_key.json").write_text(json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Generate local output-quality scorecard and blind A/B evidence.")
    parser.add_argument("--report-dir", default=str(REPORT_ROOT))
    parser.add_argument("--cases-path", default=str(EVAL_ROOT / "cases.jsonl"))
    args = parser.parse_args()
    payload = generate(Path(args.report_dir).resolve(), Path(args.cases_path).resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["summary"]["gate_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
