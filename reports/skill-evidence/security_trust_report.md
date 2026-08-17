# Security Trust Report

- OK: `True`
- Scanned files: `27`
- Scripts: `12`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `4`
- Network policy covered scripts: `4`
- Network policy missing scripts: `0`
- File-write scripts: `10`
- Permission approvals: `4 / 4`
- Permission approval gaps: `0`
- CLI help smoke checked: `9`
- CLI help smoke failures: `0`
- Interactive scripts: `1`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `27`
- Package SHA256: `8a2931c9ea00879941c8ece8fb531c2bdaf8c44d720366328d02664053c942a3`

## Failures

- None

## Warnings

- CLI scripts without argparse/help surface: scripts\common.py, scripts\platforms_fetcher.py, scripts\search_backends.py
- Interactive scripts require reviewer awareness: scripts\install_backends.py

## Dependency Evidence

- Files: `requirements.txt`
- Pinned entries: `0`
- Unpinned entries: `0`

## Network Policy

- Policy file: `security/network_policy.json`
- Present: `True`
- Covered scripts: `4`
- Missing scripts: `none`
- Mismatches: `0`

## Permission Governance

- Policy file: `security/permission_policy.json`
- Present: `True`
- Required capabilities: `file_write, interactive, network, subprocess`
- Approved capabilities: `file_write, interactive, network, subprocess`
- Missing approvals: `none`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `9`
- Passed scripts: `9`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts\collector.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\common.py | cli | False | False | False | False | True | True | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\content-archiver.py | cli | False | True | True | False | True | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\data-collector.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\env-check.py | cli | False | True | True | False | False | True | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\file2md.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\gui-panel.py | cli | False | True | True | False | False | True | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\install_backends.py | cli | False | True | True | True | False | True | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\material-manager.py | cli | False | True | True | False | False | True | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\panel-agent.py | cli | False | True | True | False | False | True | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\platforms_fetcher.py | cli | False | False | True | False | True | False | False | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
| scripts\search_backends.py | cli | False | False | True | False | True | False | True | Default CLI classification; add SCRIPT_INTERFACE for internal modules. |
