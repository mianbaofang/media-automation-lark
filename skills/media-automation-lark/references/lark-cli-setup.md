# 飞书 CLI（lark-cli）配置参考

> 涉及 lark-cli 配置或飞书 API 调用时，优先阅读本文档。所有写操作必须经由 `lark-cli` 子进程完成，禁止在脚本里直接拼 Feishu OpenAPI 的 HTTP 请求（除非 lark-cli 不可用且用户明确同意）。

## 1. 安装

```bash
npm install -g @larksuite/cli
npx skills add larksuite/cli -y -g   # 安装 AI Agent Skills
# 安装后重启你的 AI 工具（WorkBuddy / CodeBuddy 等）以使命令生效
```

验证安装：

```bash
lark-cli --version
lark-cli auth status
```

## 2. 初始化与授权

```bash
lark-cli config init              # 交互式填写应用凭证（app_id / app_secret 等）
lark-cli auth login --recommend   # 用最小权限范围登录（OAuth 2.0 Device Flow）
lark-cli auth status              # 查看当前登录身份与权限范围
```

- 凭证存储在系统原生钥匙串（Keychain / Credential Manager），不会落盘到明文文件。
- 身份切换：`lark-cli <cmd> --as bot` 以机器人身份执行；默认是用户身份。

## 3. 关键概念：app_token 与 table_id

多维表格（Bitable）写操作需要两个 ID：

- **app_token**：多维表格文档本身的 token，出现在文档 URL 中：
  `https://<domain>/base/<app_token>?table=<table_id>`
- **table_id**：文档内某个数据表的 ID，形如 `tblxxxxxxxxxxxx`（来自 URL 的 `table=` 参数，或在表格「... → 更多 → 表格信息」中查看）。

脚本配置项（`config.json` 的 `feishu` 段）：
`app_token`、`table_id`（内容归档表）、`metrics_table_id`（数据看板表）、`materials_table_id`（素材表）、`chat_id`（机器人推送群）。

## 4. 写记录到多维表格

优先使用底层 API 命令（语法稳定、字段可控）：

```bash
lark-cli api POST /open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create \
  --data '{"records":[{"fields":{"标题":"示例","链接":"https://..."}}]}'
```

> 注意：`lark-cli api` 的数据标志默认是 `--data`（见 `scripts/common.py` 的 `LARK_DATA_FLAG`；如实际为 `-d` 或 `@file` 形式，请只在此统一修改一处）。

也可使用更友好的快捷命令（命令集随版本演进，先用 `lark-cli base --help` 确认）：

```bash
lark-cli base +records-create --table-id "tblxxx" --record '{"fields":{...}}'
```

**高风险的批量写操作**可能需要 `--yes` 跳过确认，脚本已内置该标志处理。

## 5. 创建云文档（归档素材）

```bash
lark-cli docs +create --title "素材标题" --markdown "# 摘要\n- 要点1\n- 要点2"
```

返回结果含 `data.url` / `data.document_id`，脚本会回写进归档记录。

## 6. 通过机器人推送通知

```bash
lark-cli im +messages-send --as bot --chat-id "oc_xxxx" --text "今日归档完成：新增 12 条"
```

## 7. 输出契约（如何判断成功）

`lark-cli` 的 stdout 成功信封为：

```json
{ "ok": true, "identity": "...", "data": { ... }, "meta": { ... } }
```

脚本以 **`ok == true`** 判定成功（不是看 HTTP code）。失败时 `ok` 为 false 或进程非零退出，触发脚本内置重试。

## 8. 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `command not found: lark-cli` | 未全局安装或未重启工具 | 重跑安装步骤并重启 AI 工具 |
| `ok: false` / 401 | 凭证过期或权限不足 | `lark-cli auth login` 重新登录；确认 scope 含 bitable / docs / im |
| 写入无反应 | 缺少 `--yes` 或 table_id 错误 | 检查 `table_id`，开启脚本 `--yes` |
| 中文乱码 | 终端编码非 UTF-8 | 设置 `PYTHONIOENCODING=utf-8` |
