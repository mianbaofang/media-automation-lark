> Evidence mode: `temporary-staging`. Runtime files come from `skills/media-automation-lark`; eval fixtures come from `evals/`; generated reports stay in `reports/skill-evidence/` and are not installed.

# Compiled Targets

- OK: `True`
- Targets: `3`
- Pass: `3`
- Warn: `0`
- Block: `0`

## Target Transforms

| Target | Status | Native Surface | Adapter Mode | Permissions | Degradation | Generated Files |
| --- | --- | --- | --- | --- | --- | --- |
| `openai` | `pass` | OpenAI-style interface metadata plus neutral Agent Skills source | `metadata-adapter` | `network, file_write, subprocess, interactive` | `metadata-adapter` | targets/openai/adapter.json, targets/openai/agents/openai.yaml |
| `agent-skills` | `pass` | Agent Skills standard source tree | `neutral-agent-skills-source` | `network, file_write, subprocess, interactive` | `neutral-source` | SKILL.md, agents/interface.yaml |
| `generic` | `pass` | Agent Skills compatible neutral package | `agent-skills-compatible` | `network, file_write, subprocess, interactive` | `neutral-source` | targets/generic/adapter.json |

## Native Behavior Contracts

### openai

- Native surface: OpenAI-style interface metadata plus neutral Agent Skills source
- Activation: Use frontmatter description for catalog routing and targets/openai/agents/openai.yaml for display name, default prompt, and compatibility metadata.
- Resources: Ship the neutral source tree and expose OpenAI-facing interface metadata as a generated companion file.
- Scripts: Keep scripts as local package resources; expose help-smoke and permission metadata for reviewer approval before execution.
- Permission enforcement: `metadata-only`; native enforcement `False`
- Review artifacts: targets/openai/agents/openai.yaml, targets/openai/adapter.json, reports/review-studio.html

### agent-skills

- Native surface: Agent Skills standard source tree
- Activation: Use SKILL.md frontmatter name and description for progressive disclosure.
- Resources: Keep optional directories as relative resources next to SKILL.md.
- Scripts: Scripts remain local optional resources and should advertise --help when executable.
- Permission enforcement: `consumer-enforced-or-metadata-only`; native enforcement `False`
- Review artifacts: SKILL.md, agents/interface.yaml, reports/review-studio.html

### generic

- Native surface: Agent Skills compatible neutral package
- Activation: Use SKILL.md name and description; consumers decide automatic or manual activation.
- Resources: Preserve references, scripts, assets, evals, reports, and adapter metadata as relative package resources.
- Scripts: Expose script and permission metadata for downstream clients or installers to enforce.
- Permission enforcement: `consumer-enforced-or-metadata-only`; native enforcement `False`
- Review artifacts: targets/generic/adapter.json, reports/review-studio.html


## Failures

- None

## Warnings

- None
