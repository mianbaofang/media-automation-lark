# 各平台 API 接入指南

> 涉及平台数据抓取或 API Key 配置时，优先阅读本文档。核心铁律：**密钥只走环境变量或加密配置文件，严禁硬编码到脚本或提交到仓库。**

## 1. 通用设计

`scripts/common.py` 的 `require_secret(env_name, config_value)` 解析顺序：

1. 环境变量（最高优先级）：`LARK_LLM_API_KEY`、各平台 `WEIBO_API_KEY` 等。
2. `config.json` 中 `platforms.<name>.api_key` 若值为 `@env:VAR_NAME`，则从环境变量读取。
3. 两者皆空则抛出清晰错误并提示用户配置。

这样既可在 CI / 定时任务中注入密钥，也可在本地用 `.env` 文件（不提交）管理。

## 2. 平台适配清单

| 平台 | 数据类型 | 推荐接入方式 | 备注 |
|------|---------|-------------|------|
| 微博 | 博文/互动 | 开放平台 API（需审核） | 个人接口易变，优先用 RSS |
| 知乎 | 回答/文章 | 官方 API / 专栏 RSS | 专栏有 RSS |
| 小红书 | 笔记 | 公开页面解析 / 第三方 | 无官方开放 API，注意合规 |
| 微信公众号 | 文章 | 公众号 API（需认证服务号） | 或用 RSS 代理 |
| B站 | 视频/播放 | 开放平台 API | 有官方开放接口 |
| 抖音 | 视频 | 开放平台 API | 需企业资质 |
| **通用兜底** | 任意内容 | **RSS / Atom** | 大多数平台可订阅，最稳定 |

## 3. 推荐落地策略

1. **优先 RSS**：`content-archiver.py --rss-url <url>` 对任意支持 RSS 的源开箱即用，无需密钥。
2. **API 仅用于数据指标**：`data-collector.py` 读取平台开放 API 的「阅读/点赞/转发」等指标，按统一 schema 归一化。
3. **受限平台用文件喂入**：若某平台无 API，可先人工/其他工具导出 JSON/CSV，再用 `--source file.json` 喂给 `data-collector.py`。

## 4. 速率限制与重试

- 所有外网请求经过 `common.py` 的 `http_get()`，内置指数退避重试（默认 3 次，base 2s）。
- 不要在业务脚本里自行调整重试间隔——改 `common.py` 一处即可。
- 尊重 `Retry-After` 响应头与每平台 QPS 上限。

## 5. config.json 平台片段示例（仅结构，密钥走 env）

```json
{
  "platforms": {
    "weibo":    { "api_base": "https://api.weibo.com/2",        "api_key": "@env:WEIBO_API_KEY", "uid": "" },
    "bilibili": { "api_base": "https://api.bilibili.com",        "api_key": "@env:BILI_API_KEY",  "mid": "" },
    "zhihu":    { "rss_url": "https://www.zhihu.com/people/xxx/rss" }
  }
}
```
