#!/usr/bin/env python3
"""Generate portable Yao evidence without adding reports to the runtime Skill."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from package_skill import package_files, validate


PACKAGE_RELATIVE = Path("skills") / "media-automation-lark"
TARGETS = ("openai", "agent-skills", "generic")
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


def normalise_ir_paths(payload: dict[str, Any]) -> dict[str, Any]:
    for section_name in ("resources", "eval_plan"):
        section = payload.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for key, values in section.items():
            if isinstance(values, list):
                section[key] = [str(value).replace("\\", "/") for value in values]
    source_files = payload.get("source_files")
    if isinstance(source_files, list):
        payload["source_files"] = [str(value).replace("\\", "/") for value in source_files]
    return payload


def resolve_yao_root(value: str | None) -> Path:
    candidate = value or os.environ.get("YAO_META_SKILL")
    if candidate:
        return Path(candidate).expanduser().resolve()
    return (Path.home() / ".agents" / "skills" / "yao-meta-skill").resolve()


def copy_runtime_skill(root: Path, skill_root: Path, destination: Path) -> None:
    files = package_files(skill_root)
    failures = validate(root, skill_root, files)
    if failures:
        raise RuntimeError("Package validation failed before Yao staging:\n- " + "\n- ".join(failures))
    for source, relative in files:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def copy_evals(root: Path, destination: Path) -> None:
    source = root / "evals"
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(
        source,
        destination / "evals",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )


def staging_metadata() -> dict[str, Any]:
    return {
        "mode": "temporary-staging",
        "canonical_skill": "skills/media-automation-lark",
        "source_evals": "evals",
        "skill_ir": "reports/skill-evidence/skill-ir.json",
        "reason": "Yao requires package-relative IR and eval paths; GitHub CLI copies every file inside the selected Skill directory.",
    }


def add_staging_note(markdown: str) -> str:
    note = (
        "> Evidence mode: `temporary-staging`. Runtime files come from "
        "`skills/media-automation-lark`; eval fixtures come from `evals/`; "
        "generated reports stay in `reports/skill-evidence/` and are not installed.\n\n"
    )
    return note + markdown


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate portable Yao reports for the canonical Skill.")
    parser.add_argument("repo_root", nargs="?", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--yao-meta-root", default=None)
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    skill_root = (root / PACKAGE_RELATIVE).resolve()
    reports = root / "reports" / "skill-evidence"
    yao_root = resolve_yao_root(args.yao_meta_root)
    scripts = yao_root / "scripts"
    trust_script = scripts / "trust_check.py"
    governance_script = scripts / "governance_check.py"
    ir_script = scripts / "export_skill_ir.py"
    compiler_script = scripts / "compile_skill.py"
    conformance_script = scripts / "run_conformance_suite.py"
    required_files = (
        skill_root / "SKILL.md",
        trust_script,
        governance_script,
        ir_script,
        compiler_script,
        conformance_script,
    )
    for required in required_files:
        if not required.is_file():
            raise FileNotFoundError(required)
    if (skill_root / "reports").exists() or (skill_root / "evals").exists():
        raise RuntimeError("Canonical Skill must not contain reports/ or evals/; GitHub CLI would install them.")

    manifest = json.loads((skill_root / "manifest.json").read_text(encoding="utf-8"))
    generated_at = str(manifest.get("updated_at") or "")
    if not generated_at:
        raise RuntimeError("manifest.updated_at is required for reproducible compiler evidence")

    with tempfile.TemporaryDirectory(prefix="media-automation-lark-yao-") as temp_dir:
        temp_root = Path(temp_dir)
        staged_skill = temp_root / "media-automation-lark"
        copy_runtime_skill(root, skill_root, staged_skill)
        copy_evals(root, staged_skill)

        trust_json = temp_root / "security_trust_report.json"
        trust_md = temp_root / "security_trust_report.md"
        trust = run_json(
            [
                sys.executable,
                str(trust_script),
                str(skill_root),
                "--output-json",
                str(trust_json),
                "--output-md",
                str(trust_md),
            ],
            root,
        )
        governance = run_json(
            [sys.executable, str(governance_script), str(skill_root), "--require-manifest"],
            root,
        )

        generated_ir = temp_root / "skill-ir.json"
        ir_result = run_json(
            [sys.executable, str(ir_script), str(staged_skill), "--output-json", str(generated_ir)],
            root,
        )
        skill_ir = normalise_ir_paths(json.loads(generated_ir.read_text(encoding="utf-8")))
        if set(skill_ir.get("targets", [])) != set(TARGETS):
            raise RuntimeError(f"Skill IR targets do not match release targets: {skill_ir.get('targets', [])}")
        generated_ir.write_text(json.dumps(skill_ir, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        staged_reports = staged_skill / "reports"
        staged_reports.mkdir(parents=True, exist_ok=True)
        shutil.copy2(generated_ir, staged_reports / "skill-ir.json")
        shutil.copy2(trust_json, staged_reports / "security_trust_report.json")
        shutil.copy2(trust_md, staged_reports / "security_trust_report.md")

        compiled_json = temp_root / "compiled_targets.json"
        compiled_md = temp_root / "compiled_targets.md"
        compiler_command = [sys.executable, str(compiler_script), str(staged_skill)]
        for target in TARGETS:
            compiler_command.extend(["--target", target])
        compiler_command.extend(
            [
                "--output-json",
                str(compiled_json),
                "--output-md",
                str(compiled_md),
                "--generated-at",
                generated_at,
            ]
        )
        compiled = run_json(compiler_command, root)

        conformance_json = temp_root / "conformance_matrix.json"
        conformance_md = temp_root / "conformance_matrix.md"
        conformance_command = [sys.executable, str(conformance_script), str(staged_skill)]
        for target in TARGETS:
            conformance_command.extend(["--target", target])
        conformance_command.extend(
            [
                "--output-json",
                str(conformance_json),
                "--output-md",
                str(conformance_md),
            ]
        )
        conformance = run_json(conformance_command, root)

        trust_markdown = trust_md.read_text(encoding="utf-8")
        compiled_markdown = compiled_md.read_text(encoding="utf-8")
        conformance_markdown = conformance_md.read_text(encoding="utf-8")

        replacements = [
            (str(staged_skill), "skills/media-automation-lark"),
            (staged_skill.as_posix(), "skills/media-automation-lark"),
            (str(temp_root), "reports/skill-evidence"),
            (temp_root.as_posix(), "reports/skill-evidence"),
            (str(skill_root), "skills/media-automation-lark"),
            (skill_root.as_posix(), "skills/media-automation-lark"),
            (str(root), "."),
            (root.as_posix(), "."),
        ]
        trust = replace_paths(trust, replacements)
        governance = replace_paths(governance, replacements)
        skill_ir = replace_paths(skill_ir, replacements)
        compiled = replace_paths(compiled, replacements)
        conformance = replace_paths(conformance, replacements)
        trust_markdown = replace_paths(trust_markdown, replacements)
        compiled_markdown = replace_paths(compiled_markdown, replacements)
        conformance_markdown = replace_paths(conformance_markdown, replacements)

    trust["skill_dir"] = "skills/media-automation-lark"
    trust["artifacts"] = {
        "json": "reports/skill-evidence/security_trust_report.json",
        "markdown": "reports/skill-evidence/security_trust_report.md",
    }
    governance.setdefault("details", {})["skill_dir"] = "skills/media-automation-lark"
    metadata = staging_metadata()
    compiled["evidence_mode"] = metadata["mode"]
    compiled["staging_inputs"] = metadata
    compiled["artifacts"] = {
        "json": "reports/skill-evidence/compiled_targets.json",
        "markdown": "reports/skill-evidence/compiled_targets.md",
    }
    conformance["evidence_mode"] = metadata["mode"]
    conformance["staging_inputs"] = metadata
    conformance["artifacts"] = {
        "json": "reports/skill-evidence/conformance_matrix.json",
        "markdown": "reports/skill-evidence/conformance_matrix.md",
    }

    reports.mkdir(parents=True, exist_ok=True)
    outputs = {
        reports / "security_trust_report.json": json.dumps(trust, ensure_ascii=False, indent=2) + "\n",
        reports / "security_trust_report.md": trust_markdown,
        reports / "governance_report.json": json.dumps(governance, ensure_ascii=False, indent=2) + "\n",
        reports / "skill-ir.json": json.dumps(skill_ir, ensure_ascii=False, indent=2) + "\n",
        reports / "compiled_targets.json": json.dumps(compiled, ensure_ascii=False, indent=2) + "\n",
        reports / "compiled_targets.md": add_staging_note(compiled_markdown),
        reports / "conformance_matrix.json": json.dumps(conformance, ensure_ascii=False, indent=2) + "\n",
        reports / "conformance_matrix.md": add_staging_note(conformance_markdown),
    }
    for path, content in outputs.items():
        if PRIVATE_PATH.search(content):
            raise RuntimeError(f"machine-specific path remains in {display_path(path, root)}")
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {display_path(path, root)}")

    if not ir_result.get("ok") or not compiled.get("ok") or not conformance.get("ok"):
        raise RuntimeError("Yao IR, compilation, or conformance did not pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
