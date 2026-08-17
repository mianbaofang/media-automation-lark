> Evidence mode: `temporary-staging`. Runtime files come from `skills/media-automation-lark`; eval fixtures come from `evals/`; generated reports stay in `reports/skill-evidence/` and are not installed.

# Runtime Conformance Matrix

- Skill: `media-automation-lark`
- Targets: `3`
- Passed: `3`
- Failed: `0`

| Target | Status | Failures | Warnings |
| --- | --- | --- | --- |
| openai | pass | None | None |
| agent-skills | pass | None | agent-skills uses canonical Agent Skills metadata; provider-native execution transforms are not implemented in v0. |
| generic | pass | None | None |

## Reviewer Notes

- Failed targets block release for that target.
- Warnings identify lossy or not-yet-compiled behavior that must remain visible.
