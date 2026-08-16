import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills" / "media-automation-lark"
EVALS = ROOT / "evals"
REPORTS = ROOT / "reports" / "skill-evidence"
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:\\(?:Users|Object)\\|/(?:Users|home)/)", re.IGNORECASE)


def _package_module():
    path = ROOT / "tools" / "package_skill.py"
    spec = importlib.util.spec_from_file_location("media_package_skill", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_canonical_package_has_one_identity_and_required_runtime_files():
    package = _package_module()
    files = package.package_files(PACKAGE)
    assert package.validate(ROOT, PACKAGE, files) == []
    package_name = next(line for line in (PACKAGE / "SKILL.md").read_text(encoding="utf-8").splitlines() if line.startswith("name:"))
    assert package_name == "name: media-automation-lark"
    assert not (ROOT / "SKILL.md").exists()
    assert not (PACKAGE / "evals").exists()
    assert not (PACKAGE / "reports").exists()
    assert (PACKAGE / "security" / "network_policy.json").is_file()
    assert (PACKAGE / "security" / "permission_policy.json").is_file()


def test_package_declares_reproducible_trigger_evidence():
    manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
    cases_path = EVALS / "trigger_cases.json"
    config_path = EVALS / "semantic_config.json"
    output_schema_path = EVALS / "output" / "schema.json"
    output_cases_path = EVALS / "output" / "cases.jsonl"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    assert "evals" not in manifest["factory_components"]
    assert "reports" not in manifest["factory_components"]
    assert "source-repo/evals" in manifest["evidence_components"]
    assert "source-repo/reports/skill-evidence" in manifest["evidence_components"]
    assert "evals" in manifest["archive_excludes"]
    assert "audit reports" in manifest["archive_excludes"]
    assert "output eval fixtures" in manifest["archive_excludes"]
    assert cases_path.is_file()
    assert config_path.is_file()
    assert output_schema_path.is_file()
    assert output_cases_path.is_file()
    assert cases["should_trigger"]
    assert cases["should_not_trigger"]
    assert cases["near_neighbor"]


def test_public_yao_reports_do_not_expose_machine_paths():
    reports = REPORTS
    for path in reports.iterdir():
        if path.is_file():
            assert not PRIVATE_PATH.search(path.read_text(encoding="utf-8")), path


def test_private_path_detection_handles_json_escaped_windows_paths():
    package = _package_module()
    assert package.content_has_private_path("{\"output_dir\": \"E:\\\\Object\\media-automation-lark\\output_panel\"}")
    assert package.content_has_private_path(r"C:\\Users\\Ethan\\Documents")
    assert not package.content_has_private_path("{\"output_dir\": \"<project>/output_panel/output\"}")


def test_deterministic_archive_excludes_promotional_material(tmp_path, monkeypatch):
    package = _package_module()
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "315532800")
    files = package.package_files(PACKAGE)
    first = tmp_path / "one.zip"
    second = tmp_path / "two.zip"
    package.write_zip(files, first)
    package.write_zip(files, second)
    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()

    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
    assert all(name.startswith("media-automation-lark/") for name in names)
    assert not any(name.lower().endswith((".gif", ".mp4", ".webm", ".png", ".jpg", ".jpeg")) for name in names)
    assert not any("README" in name or "/reports/" in name or "/hyperframes/" in name for name in names)
    assert not any("/output_panel/" in name for name in names)
    assert not any("/evals/" in name for name in names)


def test_package_files_prunes_case_insensitive_non_runtime_trees(tmp_path):
    package = _package_module()
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    (skill_root / "safe.txt").write_text("safe", encoding="utf-8")
    for dirname in ("OUTPUT_PANEL", "Reports", "HyperFrames", "MP4", "Media"):
        excluded = skill_root / dirname
        excluded.mkdir()
        (excluded / "should-not-be-read.txt").write_text("excluded", encoding="utf-8")
    eval_output = skill_root / "evals" / "OUTPUT"
    eval_output.mkdir(parents=True)
    (eval_output / "should-not-be-read.txt").write_text("excluded", encoding="utf-8")

    packaged = [relative.as_posix() for _, relative in package.package_files(skill_root)]
    assert packaged == ["safe.txt"]


def test_archive_members_reject_unsafe_and_duplicate_paths(tmp_path):
    package = _package_module()
    skill = tmp_path / "SKILL.md"
    skill.write_text("name: media-automation-lark\n", encoding="utf-8")

    for unsafe in (Path(""), Path("../escape.txt"), Path("C:/escape.txt"), Path("/escape.txt")):
        with pytest.raises(ValueError):
            package.write_zip(
                [(skill, Path("SKILL.md")), (skill, unsafe)],
                tmp_path / "unsafe.zip",
            )

    with pytest.raises(ValueError, match="duplicate archive member"):
        package.write_zip(
            [
                (skill, Path("SKILL.md")),
                (skill, Path("Guide.txt")),
                (skill, Path("guide.txt")),
            ],
            tmp_path / "duplicate.zip",
        )

    with pytest.raises(ValueError, match="root-level SKILL.md"):
        package.write_zip(
            [(skill, Path("SKILL.md")), (skill, Path("nested/SKILL.md"))],
            tmp_path / "nested-skill.zip",
        )


def test_package_builder_blocks_sensitive_files_and_excludes_readmes(tmp_path):
    package = _package_module()
    skill_root = tmp_path / "skill"
    skill_root.mkdir()
    (skill_root / "README.en.md").write_text("documentation", encoding="utf-8")
    (skill_root / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (skill_root / "credentials.json").write_text("{}", encoding="utf-8")
    (skill_root / "safe.txt").write_text("safe", encoding="utf-8")

    packaged = [relative.as_posix() for _, relative in package.package_files(skill_root)]
    assert packaged == ["safe.txt"]
    assert package.sensitive_reason(Path(".env")) == "environment file"
    assert package.sensitive_reason(Path("credentials.json")) == "credential-like filename"
    assert package.is_readme(Path("README.en.md"))
