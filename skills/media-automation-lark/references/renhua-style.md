# 文本润色（renhua / 人话）

本 skill 产出的所有中文文字都先经 `renhua`（人话）去 AI 味改写，再对外输出。本文件说明它是什么、怎么装、怎么接、怎么关。

## renhua 是什么

`renhua`（人话）是 GitHub 仓库 [Pluviobyte/rnskill](https://github.com/Pluviobyte/rnskill) 里的一个**提示词型 Agent 技能**，不是命令行工具。它是一套中文 AI/技术写作"去 AI 味"的改写规则：保留事实、数字、专名与作者判断，去掉「不是 A 而是 B」式二元对比壳、「真正/其实/本质上/关键在于」等伪洞察词、冒号讲义腔和空泛总结。

因为是非 CLI 技能，本 skill 不能 `subprocess` 直接调用它，而是：

1. **安装时**把 `skills/renhua` 拉到用户 skills 目录；
2. **运行时**由 `common.polish_text()` 调 LLM，并把 `renhua/SKILL.md` 的正文作为 system prompt，让 LLM 套用其规则改写文字。

## 安装

- 一键：`python3 scripts/env-check.py --auto-install`（已装的自动跳过）
- 单独：`python3 scripts/install_backends.py renhua` 或 `--all`
- 手动：`git clone --depth 1 https://github.com/Pluviobyte/rnskill`，把其中 `skills/renhua` 复制到 `~/.workbuddy/skills/renhua`（或 `~/.agents/skills/renhua`）。

检测是否装好：`python3 scripts/env-check.py` 末尾的「文本润色」一行，或 `python3 -c "import sys; sys.path.insert(0,'scripts'); import common; print(common.find_renhua_skill())"`。

## 规则来源（单一事实源）

`common.load_polish_rules()` 运行时读取已安装的 `renhua/SKILL.md`（去掉 YAML frontmatter）作改写规则。未安装时退回 `common._RENHUA_FALLBACK`（内置精简规则），保证无网/未装也能跑、只是风格弱一些。

不要在本 skill 里另写一套风格规则——以 `renhua/SKILL.md` 为准，保持单一事实源。

## 接入点

`common.polish_text(text, config)` 是统一入口，已接入：

| 场景 | 润色的文字 |
|------|-----------|
| A 内容存档 | 提取的 `summary`、核心观点 |
| C 多模态素材 | 分析的 `summary`、`key_points`、`action_items`、`reuse_suggestion` |
| D 搜索采集 | 索引 `index.md` 的简介；`--polish-body` 时连抓取正文也润色 |

抓取到的**原文正文默认不润色**（`text.polish_body=false`），以保证归档真实性——你存的是别人的文章，不该被改写。只润色本 skill 自己生成的文字。

## 开关与降级

- `config.json` 的 `text.polish`（默认 `true`）：总开关。
- 场景 D 额外：`--no-polish` 关闭本次润色；`--polish-body` 连正文一起润色。
- **降级**：未配 LLM key（`LARK_LLM_API_KEY`）或 LLM 调用失败，`polish_text` 原样返回文字，不阻断流程。

## Agent（助手）层面

当本助手就该 skill 的交付物写回复（总结、说明）时，也应套用 renhua 风格：直接、具体、保留判断，不用 AI 腔模板。renhua 技能安装后，助手可直接加载其规则。
