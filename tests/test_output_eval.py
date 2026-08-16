import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GENERATOR = ROOT / "tools" / "generate_output_eval_reports.py"


def test_output_eval_generates_reproducible_local_evidence():
    with tempfile.TemporaryDirectory(prefix="media-automation-lark-output-test-") as tmp:
        tmp_root = Path(tmp)
        report_dir = tmp_root / "reports"
        cases_path = tmp_root / "cases.jsonl"
        proc = subprocess.run(
            [sys.executable, str(GENERATOR), "--report-dir", str(report_dir), "--cases-path", str(cases_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        payload = json.loads(proc.stdout)

        assert payload["ok"] is True
        assert payload["provider_backed"] is False
        assert payload["summary"]["case_count"] == 5
        assert payload["summary"]["file_backed_case_count"] == 4
        assert payload["summary"]["near_neighbor_case_count"] == 1
        assert payload["summary"]["boundary_case_count"] == 1
        assert payload["summary"]["with_skill_pass_rate"] == 100.0
        assert payload["summary"]["with_skill_pass_rate"] > payload["summary"]["baseline_pass_rate"]
        assert payload["summary"]["regression_count"] == 0
        assert payload["summary"]["blind_pair_count"] == 5

        cases = [json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(cases) == 5
        case_text = cases_path.read_text(encoding="utf-8")
        assert "C:\\Users" not in case_text
        assert "C:/Users" not in case_text
        assert "C://Users" not in case_text
        assert "E:\\Object" not in case_text
        assert "E:/Object" not in case_text
        assert "media-automation-lark-output-eval-" not in case_text
        assert "DURATION_MS=<elapsed>" in case_text
        assert "<!doctype" not in case_text.casefold()
        assert "<style>" not in case_text.casefold()
        for case in cases:
            assert case["execution"]["mode"] == "command"
            assert case["execution"]["provider_backed"] is False
            for relative in case.get("input_files", []):
                assert (ROOT / "skills" / "media-automation-lark" / "evals" / "output" / relative).exists()

        blind_text = (report_dir / "output_blind_review_pack.json").read_text(encoding="utf-8")
        assert "variant_a_role" not in blind_text
        assert "variant_b_role" not in blind_text
        answer_text = (report_dir / "output_blind_answer_key.json").read_text(encoding="utf-8")
        assert "variant_a_role" in answer_text
        assert "variant_b_role" in answer_text

        scorecard = (report_dir / "output_quality_scorecard.md").read_text(encoding="utf-8")
        assert "Output Quality Scorecard" in scorecard
        assert "Provider-backed evidence: `false`" in scorecard
        assert "Failure Taxonomy" in scorecard
        blind_markdown = (report_dir / "output_blind_review_pack.md").read_text(encoding="utf-8")
        assert "Output Blind A/B Review Pack" in blind_markdown
        assert "Answer key separate: `true`" in blind_markdown

        panel = next(case for case in cases if case["id"] == "panel-safe-default")
        assert "<style>" not in panel["with_skill_output"]
        assert "<!doctype" not in panel["with_skill_output"].casefold()
        assert len(panel["with_skill_output"]) < 5000


def test_cases_keep_unsafe_url_boundary_evidence():
    with tempfile.TemporaryDirectory(prefix="media-automation-lark-output-test-") as tmp:
        cases_path = Path(tmp) / "cases.jsonl"
        report_dir = Path(tmp) / "reports"
        subprocess.run(
            [sys.executable, str(GENERATOR), "--report-dir", str(report_dir), "--cases-path", str(cases_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        cases = {json.loads(line)["id"]: json.loads(line) for line in cases_path.read_text(encoding="utf-8").splitlines() if line.strip()}
        unsafe = cases["unsafe-url-boundary"]["with_skill_output"]
        assert "拒绝不安全 RSS URL" in unsafe
        assert "SSRF 防护" in unsafe
        assert "EXIT_CODE=1" in unsafe
        assert "写入飞书" not in unsafe
