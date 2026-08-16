#!/usr/bin/env python3
"""Generate portable Yao governance and trust reports for the canonical Skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PACKAGE_RELATIVE = Path("skills") / "media-automation-lark"
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:\\(?:Users|Object)\\|/(?:Users|home)/)", re.IGNORECASE)


def run_json(command: list[str], cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Yao report command failed")
    return json.loads(result.stdout)


def replace_paths(value: Any, replacements: list[tuple[str, str]]) -> Any:
    if isinstance(value, dict):
        return {key: replace_paths(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_paths(item, replacements) for item in value]
    if isinstance(value, str):
        for source, target in replacements:
            value = value.replace(source, target)
        return value
    return value


def resolve_yao_root(value: str | None) -> Path:
    candidate = value or os.environ.get("YAO_META_SKILL")
    if candidate:
        return Path(candidate).expanduser().resolve()
    return (Path.home() / ".agents" / "skills" / "yao-meta-skill").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate path-portable Yao reports for the canonical Skill.")
    parser.add_argument("repo_root", nargs="?", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--yao-meta-root", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    skill_root = (root / PACKAGE_RELATIVE).resolve()
    reports = root / "reports" / "skill-evidence"
    yao_root = resolve_yao_root(args.yao_meta_root)
    trust_script = yao_root / "scripts" / "trust_check.py"
    governance_script = yao_root / "scripts" / "governance_check.py"
    for required in (skill_root / "SKILL.md", trust_script, governance_script):
        if not required.is_file():
            raise FileNotFoundError(required)

    with tempfile.TemporaryDirectory(prefix="media-automation-lark-yao-") as temp_dir:
        temp_root = Path(temp_dir)
        temp_json = temp_root / "security_trust_report.json"
        temp_md = temp_root / "security_trust_report.md"
        trust = run_json(
            [
                sys.executable,
                str(trust_script),
                str(skill_root),
                "--output-json",
                str(temp_json),
                "--output-md",
                str(temp_md),
            ],
            root,
        )
        governance = run_json(
            [sys.executable, str(governance_script), str(skill_root), "--require-manifest"],
            root,
        )
        trust_markdown = temp_md.read_text(encoding="utf-8")

    replacements = [
        (str(skill_root), "."),
        (skill_root.as_posix(), "."),
        (str(root), "."),
        (root.as_posix(), "."),
    ]
    trust = replace_paths(trust, replacements)
    governance = replace_paths(governance, replacements)
    trust["skill_dir"] = "skills/media-automation-lark"
    trust["artifacts"] = {
        "json": "reports/skill-evidence/security_trust_report.json",
        "markdown": "reports/skill-evidence/security_trust_report.md",
    }
    governance.setdefault("details", {})["skill_dir"] = "skills/media-automation-lark"
    trust_markdown = replace_paths(trust_markdown, replacements)

    reports.mkdir(parents=True, exist_ok=True)
    outputs = {
        reports / "security_trust_report.json": json.dumps(trust, ensure_ascii=False, indent=2) + "\n",
        reports / "security_trust_report.md": trust_markdown,
        reports / "governance_report.json": json.dumps(governance, ensure_ascii=False, indent=2) + "\n",
    }
    for path, content in outputs.items():
        if PRIVATE_PATH.search(content):
            raise RuntimeError(f"machine-specific path remains in {path.relative_to(root)}")
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
