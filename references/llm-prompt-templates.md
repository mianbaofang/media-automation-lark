# LLM Prompt 模板

> 优化 LLM 提取/分析准确率时，优先阅读本文档。所有模板由 `scripts/common.py` 的 `llm_chat()` 调用，接口为 OpenAI 兼容的 Chat Completions（在 `config.json` 配置 `llm.api_base` / `llm.model`）。

## 公共约束（每条 user 消息都追加）

- 只输出 JSON，不要解释、不要 markdown 代码块围栏。
- 字段缺失时填 `null`，不要编造。
- 中文内容保持原语言，不要翻译。

## 1. 内容结构化提取（content-archiver.py）

System：
```
你是一个自媒体内容结构化提取器。给定一篇文章的标题、正文摘要与链接，提取以下字段并以 JSON 返回：
{
  "title": "标题",
  "author": "作者/来源",
  "published_at": "发布时间 ISO8601，无法识别则 null",
  "summary": "80 字以内中文摘要",
  "category": "从[科技,财经,生活,教育,娱乐,其他]选一",
  "tags": ["标签1","标签2"],
  "sentiment": "从[正面,中性,负面]选一",
  "word_count": 整数,
  "key_points": ["核心观点1","核心观点2"]
}
```

Few-shot（可选）：附 1 个已标注样例可显著提升稳定性。

## 2. 素材智能分析（material-manager.py）

- 文章链接：同「内容提取」，但增加 `action_items`（可落地的行动项）。
- 图片：若配置了视觉模型（见 `llm.vision_model`），发送 base64 图片，返回
  `{ "description": "...", "objects": [...], "text_in_image": "...", "suitable_for": "适用场景" }`。
- PDF：提取全文后按「文章链接」模板总结，额外返回 `page_count`。

## 3. 指标洞察（data-collector.py）

System：
```
你是一个新媒体数据分析师。给定某平台一段时间的核心指标（阅读/播放、点赞、评论、转发、新增粉丝），
输出 JSON：
{
  "best_performer": "表现最好的内容标题或 null",
  "trend": "从[上升,平稳,下降]选一",
  "insight": "一句话运营洞察",
  "recommendation": "一句可执行建议"
}
```

## 4. 调优建议

- 准确率低 → 增加 few-shot、收紧 `category` 枚举、明确 `null` 规则。
- 输出非 JSON → 在 `llm_chat()` 中启用 `response_format={"type":"json_object"}`（若模型支持），并做 `json.loads` 容错解析。
- 成本高 → 降 `llm.model` 到低配、缩短 `summary` 字数。

## 5. 输出去 AI 味（renhua）

提取/分析产出的中文摘要、要点、行动项，写盘前经 `common.polish_text(text, config)` 二次润色（默认 `text.polish=true`）。规则来自已安装的 `renhua/SKILL.md`（单一事实源）；未装则用 `common._RENHUA_FALLBACK` 内置精简规则；无 LLM key 时原样返回。详见 `references/renhua-style.md`。不要在提取 Prompt 里另写一套风格规则——润色是独立的后处理步骤。
