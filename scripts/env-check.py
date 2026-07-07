#!/usr/bin/env python3
"""环境检测与依赖安装，并生成 config.json.example 模板。

用法：
  python3 env-check.py                 # 仅检测，不安装
  python3 env-check.py --auto-install  # 检测并自动安装缺失依赖
  python3 env-check.py --gen-config    # 仅生成 config.json.example 模板
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys

PY_PKGS = ["requests", "feedparser", "beautifulsoup4", "pandas", "openpyxl", "python-docx", "PyPDF2", "markitdown"]
# 导入名与包名可能不同
IMPORT_MAP = {
    "requests": "requests",
    "feedparser": "feedparser",
    "beautifulsoup4": "bs4",
    "pandas": "pandas",
    "openpyxl": "openpyxl",
    "python-docx": "docx",
    "PyPDF2": "PyPDF2",
    "markitdown": "markitdown",
}
# 需要 extras 的包：缺失时以「带 extras」的形式安装（普通包照原样）
PIP_EXTRAS = {
    "markitdown": "markitdown[all]",  # 场景C文件入库需要 pdf/docx/pptx/xlsx/epub 等转换器
}

CONFIG_EXAMPLE = {
    "feishu": {
        "app_token": "basetoken_from_url",
        "table_id": "tbl_content_archive",
        "archive_table_id": "tbl_content_archive",
        "metrics_table_id": "tbl_metrics",
        "materials_table_id": "tbl_materials",
        "chat_id": "oc_xxxx",
        "lark_cli_path": "lark-cli",
        "data_flag": "--data",
    },
    "llm": {
        "env_key": "LARK_LLM_API_KEY",
        "api_key": "@env:LARK_LLM_API_KEY",
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "vision_model": "",
        "timeout": 60,
    },
    "platforms": {
        "weibo": {"api_base": "https://api.weibo.com/2", "api_key": "@env:WEIBO_API_KEY", "uid": ""},
        "bilibili": {"api_base": "https://api.bilibili.com", "api_key": "@env:BILI_API_KEY", "mid": ""},
    },
    "search": {
        "queries": ["LLM 应用落地", "Agent 工作流"],
        "category_map": "AI:大模型,LLM,Agent;产品:增长,PM,运营;技术:Python,架构,RAG",
        "default_category": "综合",
        "backends": "",
        "rss_urls": [],
    },
    "text": {
        "polish": True,
        "polish_body": False
    },
    "paths": {"output_dir": "./output"},
    "notify": {"enabled": True},
}


def have_python_pkg(pkg: str) -> bool:
    mod = IMPORT_MAP.get(pkg, pkg)
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def have_cmd(name: str) -> bool:
    return shutil.which(name) is not None


def pip_install(pkgs: list[str]) -> None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs])


def gen_config(path: str) -> None:
    if os.path.isfile(path):
        print(f"[跳过] 已存在 {path}")
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(CONFIG_EXAMPLE, f, ensure_ascii=False, indent=2)
    print(f"[生成] {path}（请复制为 config.json 并填写，密钥用 @env: 占位）")


def main() -> None:
    p = argparse.ArgumentParser(description="自媒体自动化工作流 · 环境检测")
    p.add_argument("--auto-install", action="store_true", help="自动安装缺失依赖（含搜索后端）")
    p.add_argument("--install-search-backends", action="store_true", help="从 GitHub 拉取缺失的搜索后端")
    p.add_argument("--gen-config", action="store_true", help="生成 config.json.example 模板")
    p.add_argument("--config-out", default=None, help="config 模板输出目录（默认项目根目录）")
    args = p.parse_args()

    print("=== Python 环境 ===")
    print(f"Python: {sys.version.split()[0]} @ {sys.executable}")

    missing_py: list[str] = []
    for pkg in PY_PKGS:
        ok = have_python_pkg(pkg)
        print(f"  [{'OK' if ok else 'MISSING'}] {pkg}")
        if not ok:
            missing_py.append(pkg)

    print("\n=== Node / lark-cli ===")
    node_ok = have_cmd("node")
    npm_ok = have_cmd("npm")
    lark_ok = have_cmd("lark-cli")
    print(f"  [{'OK' if node_ok else 'MISSING'}] node")
    print(f"  [{'OK' if npm_ok else 'MISSING'}] npm")
    print(f"  [{'OK' if lark_ok else 'MISSING'}] lark-cli")

    print("\n=== 搜索后端（运行时检测，缺失会跳过而非崩溃）===")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import search_backends as sb
    for name, s in sb.detect().items():
        flag = "OK" if (s["installed"] and s["working"]) else ("INSTALLED" if s["installed"] else "MISSING")
        print(f"  [{flag}] {name:12s} {s['label']}  — {s['note']}")

    print("\n=== 文本润色（renhua / 人话 · 去 AI 味）===")
    import common as _common
    rh = _common.find_renhua_skill()
    print(f"  [{'OK' if rh else 'MISSING'}] renhua  — {rh or '未安装，运行 --auto-install 从 GitHub 拉取'}")

    print("\n=== 外部 skill 缺失汇总 ===")
    import install_backends as _ib
    missing_ext = [n for n in list(_ib.INSTALL_PLAN) if not _ib.is_present(n)]
    if missing_ext:
        print("缺失: " + ", ".join(missing_ext))
        print("  逐项确认安装: python3 scripts/install_backends.py --interactive")
        print("  或全部安装:   python3 scripts/install_backends.py --all")
    else:
        print("全部外部 skill 已就绪")

    out_dir = args.config_out or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    example_path = os.path.join(out_dir, "config.json.example")
    if args.gen_config:
        gen_config(example_path)
        return

    if args.auto_install or args.install_search_backends:
        if missing_py:
            print(f"\n[安装] Python 依赖: {missing_py}")
            pkgs_to_install = [PIP_EXTRAS.get(p, p) for p in missing_py]
            pip_install(pkgs_to_install)
        if not lark_ok:
            print("\n[安装] @larksuite/cli（需全局，可能要求 sudo）")
            try:
                subprocess.check_call(["npm", "install", "-g", "@larksuite/cli"])
                print("  安装完成，请运行：lark-cli config init && lark-cli auth login --recommend")
            except Exception as e:  # noqa: BLE001
                print(f"  自动安装失败（需 npm 全局权限）：{e}")
                print("  手动执行：npm install -g @larksuite/cli && npx skills add larksuite/cli -y -g")
        if args.auto_install or args.install_search_backends:
            print("\n[安装] 搜索后端（已装的跳过）")
            import install_backends
            install_backends.install(list(install_backends.INSTALL_PLAN), force=False)
        gen_config(example_path)

    print("\n=== 配置校验 ===")
    try:
        cfg = _common.load_config(None)
        warns = _common.validate_config(cfg)
        for w in warns:
            print(f"  ⚠ {w}")
        if not warns:
            print("  OK")
    except Exception as e:  # noqa: BLE001
        print(f"  跳过（{e}）")

    print("\n=== 结论 ===")
    search_ok = any(s.get("installed") and s.get("working") for s in sb.detect().values())
    if missing_py or not lark_ok:
        print("存在缺失依赖。运行 `python3 env-check.py --auto-install` 自动补齐，")
        print("并参阅 references/lark-cli-setup.md 完成飞书 CLI 授权。")
        sys.exit(1)
    print("场景 A/B/C：就绪（运行前需在 config.json 配置飞书 app_token/table_id）。")
    print(f"场景 D（搜索采集→分类 Markdown）：{'就绪' if search_ok else '缺可用搜索后端——运行 install_backends.py --all'}。")
    print("下一步：复制 config.json.example 为 config.json 并填写，")
    print("然后按 SKILL.md 选择场景运行对应脚本。")


if __name__ == "__main__":
    main()
