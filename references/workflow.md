# 详细工作流参考

本文件承接 `SKILL.md` 的详细操作说明。先读取它，再按用户的场景选择脚本；所有真实写入前都先做本地预览。

## 初始化

```bash
python3 scripts/env-check.py --auto-install
cp config.json.example config.json
python3 scripts/install_backends.py --interactive
```

配置文件只放 `@env:VAR_NAME` 占位符，不写入密钥。飞书写入前读取
`references/lark-cli-setup.md`，完成 `lark-cli config init` 与
`lark-cli auth login --recommend`。缺少可选搜索后端时跳过或降级，不要因为某个后端未安装就判定整个 Skill 不可用。

## 场景选择

| 场景 | 入口 | 结果 |
|---|---|---|
| 内容归档 | `scripts/content-archiver.py` | RSS/API 内容结构化、去重、备份并可写入飞书多维表格 |
| 数据与看板 | `scripts/data-collector.py` | 平台指标、互动率、HTML 看板和可选飞书同步 |
| 素材管理 | `scripts/material-manager.py` | 文章、图片、PDF、Office 文件转 Markdown，分析后归档飞书云文档 |
| 搜索采集 | `scripts/collector.py` | 按选题搜索、抓正文、分类保存 Markdown，可选归档飞书 |
| 新手面板 | `scripts/panel-agent.py start --open` | 启动本地控制台，返回面板 URL；默认只做预览 |

用户说“不会用”“打开面板”“开始配置”或“先检查环境”时，Agent 直接启动面板，不要求用户手写命令。面板的六个任务是环境检查、安全样例、网页/文件整理、选题采集、RSS 归档、看板和定时准备。

## 推荐顺序

1. 先阅读 `DISCLAIMER.md`，再读本文件和匹配的参考文档。
2. 先运行 `--dry-run`；搜索场景先用 `--offline-demo` 验证分类和 Markdown 格式。
3. 检查本地产物、去重结果、分类和摘要后，才允许用户明确要求的飞书写入。
4. 定时任务只复用 `assets/cron-examples/`，不要在对话里重写重试或调度逻辑。

常用示例：

```bash
python3 scripts/collector.py --offline-demo --output-dir output_demo --no-archive --no-notify
python3 scripts/content-archiver.py --rss-url "https://example.com/feed.xml" --dry-run
python3 scripts/collector.py --query "LLM 应用落地" --rank-by hotness --dry-run
python3 scripts/data-collector.py --fetch --platform bilibili --dry-run
python3 scripts/material-manager.py --file "./report.pdf" --dry-run
```

## 搜索与文字

运行时检测 `anysearch`、`tavily`、`autocli`、`agent-reach`、`multi-search-engine` 和内置 HTTP 兜底。`agent-reach` 与 `multi-search-engine` 只在交互编排中使用，不进无头定时脚本。搜索采集支持来源范围、排序目标、分类映射、`--no-fetch` 和后端限定；没有后端且没有 RSS 时明确退出并给出安装提示。

本 Skill 生成的中文摘要、标题、索引和通知默认经已安装的 `renhua/SKILL.md` 规则润色；抓取正文保留原文。无 LLM key 或润色失败时原样返回，不阻断归档。

## 边界

- URL 入口必须经过 `common.is_safe_url`；拒绝 `file://`、loopback、私网和云元数据地址，除非用户明确开启私网测试。
- 密钥只来自环境变量或 `@env:`；不绕过验证码、登录限制、付费墙、加密或平台风控。
- 扫描和抓取源文件默认只读；输出写入用户选择的本地目录，飞书写入必须显式确认。
- RSS/API 与平台数据可能受限、延迟或缺字段；缺失时保留降级说明，不虚构结果。

匹配专题时再读取 `references/api-integration.md`、`references/llm-prompt-templates.md`、`references/search-backends.md`、`references/renhua-style.md` 和 `references/lark-cli-setup.md`。
