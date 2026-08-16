# Output Quality Scorecard

This report compares explicit static baseline text with outputs produced by fixed local scripts.
It is local command evidence, not provider-backed model evidence.

- Cases: `5`
- File-backed cases: `4`
- Near-neighbor cases: `1`
- Boundary cases: `1`
- Baseline pass rate: `0.0`
- With-skill pass rate: `100.0`
- Delta: `100.0`
- Regressions: `0`
- Blind A/B pairs: `5`
- Provider-backed evidence: `false`
- Gate pass: `true`

## Case Results

| Case | Baseline | With Skill | Delta | Winner | Failed With-Skill Assertions |
| --- | ---: | ---: | ---: | --- | --- |
| offline-search-archive | 0.0 | 100.0 | 100.0 | with_skill | None |
| metrics-dashboard | 0.0 | 100.0 | 100.0 | with_skill | None |
| material-local-preview | 0.0 | 100.0 | 100.0 | with_skill | None |
| panel-safe-default | 0.0 | 100.0 | 100.0 | with_skill | None |
| unsafe-url-boundary | 0.0 | 100.0 | 100.0 | with_skill | None |

## Failure Taxonomy

- No with-skill assertion failures.

## Evidence Boundary

- The baseline is a documented static comparison string, not a historical run.
- The with-skill outputs come from the repository's offline scripts and fixed fixtures.
- No API key, external model, network fetch, download metric, or human blind-review decision is claimed here.
- The separate blind pack must be reviewed before opening the answer key.

## Next Fixes

- Add holdout fixtures before using this as a long-term release gate.
- Record reviewer decisions separately with a rubric-based reason.
