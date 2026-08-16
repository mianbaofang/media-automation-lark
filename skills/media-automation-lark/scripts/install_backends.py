#!/usr/bin/env python3
"""安装时下载缺失的搜索后端（从 GitHub / 官方安装脚本）。

直接回答用户的顾虑：搜索工具没装，skill 就废了。
本脚本在「初次安装」或「--auto-install」时调用，把缺的后端拉到用户机器；
已装的自动跳过（幂等），不会重复下载。

用法：
  python scripts/install_backends.py --all
  python scripts/install_backends.py anysearch tavily
  python scripts/install_backends.py --all --dry-run     # 只打印将做什么
  python scripts/install_backends.py --all --skills-root D:/skills
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_backends as sb


# 安装清单：搜索/润色后端（GitHub skill）与 pip 包都在这里登记。
# 注意：markitdown 是 pip 包（非 GitHub skill），单独以 method="pip" 处理。
INSTALL_PLAN = {
    "markitdown": {
        "method": "pip",
        "pkg": "markitdown[all]",
        "import": "markitdown",
        "hint": "文件转 Markdown 库（pip 包，非 GitHub skill）；场景C 本地文件素材入库 PDF/DOCX/PPTX/XLSX/EPUB/HTML/音频",
    },
    "anysearch": {
        "method": "git",
        "url": "https://github.com/anysearch-ai/anysearch-skill",
        "target": "anysearch",
        "hint": "也可 npx skills add 或下载 release zip: https://github.com/anysearch-ai/anysearch-skill/releases",
    },
    "tavily": {
        "method": "curl",
        "url": "https://cli.tavily.com/install.sh",
        "hint": "CLI: curl -fsSL https://cli.tavily.com/install.sh | bash; skill: npx skills add https://github.com/tavily-ai/skills; 需 TAVILY_API_KEY (tvly login 或环境变量)",
    },
    "autocli": {
        "method": "curl",
        "url": "https://raw.githubusercontent.com/nashsu/AutoCLI/main/scripts/install.sh",
        "hint": "二进制见 https://github.com/nashsu/AutoCLI/releases; skill 文档见 https://github.com/nashsu/AutoCLI-skill; Windows 到 releases 下载",
    },
    "agent_reach": {
        "method": "git",
        "url": "https://github.com/Panniantong/Agent-Reach",
        "target": "agent-reach",
    },
    "multi_search": {
        "method": "marketplace",
        "hint": "通过 WorkBuddy 技能市场安装 multi-search-engine（无单一 git 仓库）",
    },
    "renhua": {
        "method": "git_skill",
        "url": "https://github.com/Pluviobyte/rnskill",
        "subpath": "skills/renhua",
        "target": "renhua",
        "hint": "人话/去AI味改写技能；安装后本 skill 对外文字自动经其润色",
    },
}


def skills_root_arg(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    for p in [
        Path.home() / ".workbuddy" / "skills",
        Path.home() / ".agents" / "skills",
    ]:
        if p.exists():
            return p
    return Path.home() / ".workbuddy" / "skills"


def is_present(name: str) -> bool:
    if name == "renhua":
        import common as _c
        return _c.find_renhua_skill() is not None
    # pip 类（如 markitdown）：按导入名判断是否已装
    plan = INSTALL_PLAN.get(name)
    if plan and plan.get("method") == "pip":
        import importlib

        try:
            importlib.import_module(plan.get("import", name))
            return True
        except Exception:
            return False
    b = sb.REGISTRY.get(name)
    return bool(b and b.is_installed())


def run(cmd, **kw):
    print("  $ " + " ".join(cmd))
    if kw.pop("dry", False):
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, **kw)


def install_one(name: str, root: Path, dry: bool, force: bool) -> str:
    if name not in INSTALL_PLAN:
        return f"✗ 未知后端 {name}（可选：{', '.join(INSTALL_PLAN)}）"
    if is_present(name) and not force:
        return f"○ 已安装，跳过（{name}）"

    plan = INSTALL_PLAN[name]
    method = plan["method"]
    if method == "git":
        target = root / plan["target"]
        if target.exists() and not force:
            return f"○ 目录已存在，跳过（{target}）"
        run(["git", "clone", "--depth", "1", plan["url"], str(target)], dry=dry)
        return f"✓ git 克隆完成：{target}"
    if method == "curl":
        url = plan["url"]
        if dry:
            print(f"  $ curl -fsSL {url} | sh   (dry-run)")
            return f"✓（dry）将运行 curl 安装脚本：{url}"
        # 直接下载脚本让用户确认后再执行，避免静默管道执行远程脚本
        print(f"  请从官方地址安装 {name}：")
        print(f"    curl -fsSL {url} | sh")
        if plan.get("hint"):
            print(f"  注：{plan['hint']}")
        return f"⏳ 需手动执行安装脚本（{name}）— 见上方命令"
    if method == "marketplace":
        print(f"  {plan.get('hint', '')}")
        return f"⏳ 需通过技能市场安装（{name}）"
    if method == "pip":
        import importlib

        mod = plan.get("import", name)
        try:
            importlib.import_module(mod)
            if not force:
                return f"○ 已安装，跳过（{name}）"
        except Exception:
            pass
        if dry:
            print(f"  $ pip install {plan['pkg']}   (dry-run)")
            return f"✓（dry）将 pip 安装：{plan['pkg']}"
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", plan["pkg"]])
        except Exception as ex:  # noqa: BLE001
            return f"✗ pip 安装失败：{ex}"
        return f"✓ pip 安装完成：{plan['pkg']}"
    if method == "git_skill":
        target = root / plan["target"]
        if target.exists() and not force:
            return f"○ 目录已存在，跳过（{target}）"
        import tempfile

        tmp = tempfile.mkdtemp(prefix="rnskill_")
        run(["git", "clone", "--depth", "1", plan["url"], tmp], dry=dry)
        src = Path(tmp) / plan["subpath"]
        if dry:
            return f"✓（dry）将复制 {src} -> {target}"
        if not src.exists():
            return f"✗ 仓库内未找到 {plan['subpath']}"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src, target)
        shutil.rmtree(tmp, ignore_errors=True)
        return f"✓ 已安装 {name} 到 {target}"
    return f"✗ 未知安装方式：{method}"


def install(names: list[str], skills_root: str | None = None, dry: bool = False, force: bool = False, interactive: bool = False) -> None:
    """可调用入口（供 env-check 等复用），不含 argparse。"""
    root = skills_root_arg(skills_root)
    root.mkdir(parents=True, exist_ok=True)
    print(f"技能根目录: {root}")

    print("【安装计划】")
    for n in names:
        if is_present(n) and not force:
            print(f">> {n}: 已安装，跳过")
            continue
        if interactive and not force:
            try:
                ans = input(f">> 缺失 {n}，是否自动安装？[Y/n] ").strip().lower()
            except EOFError:
                ans = "n"
            if ans in ("n", "no"):
                print(f"   跳过 {n}")
                continue
        print(f"\n>> {n}")
        try:
            msg = install_one(n, root, dry, force)
        except Exception as ex:  # noqa: BLE001
            msg = f"✗ 失败：{ex}"
        print(f"   {msg}")

    print("\n【安装后检测】")
    for n in names:
        plan = INSTALL_PLAN.get(n)
        if plan and plan.get("method") == "pip":
            print(f"  {'✓' if is_present(n) else '○'} {n}: {plan['pkg']}")
            continue
        b = sb.REGISTRY.get(n)
        if b:
            s = sb.detect().get(n, {})
            print(f"  {'✓' if s.get('installed') and s.get('working') else '○'} {n}: {s.get('note','')}")
    if "renhua" in names:
        import common as _common

        rp = _common.find_renhua_skill()
        print(f"  {'✓' if rp else '○'} renhua: {rp or '未安装'}")


def main():
    p = argparse.ArgumentParser(description="安装搜索后端（GitHub 下载）")
    p.add_argument("names", nargs="*", help="后端名；省略或 --all 表示全部")
    p.add_argument("--all", action="store_true")
    p.add_argument("--skills-root", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true", help="已装的也重新拉取")
    p.add_argument("--interactive", action="store_true", help="逐项确认安装（缺失才问，适合人工）")
    a = p.parse_args()

    names = a.names if a.names else (list(INSTALL_PLAN) if a.all else [])
    if not names:
        print("未指定后端。用法：install_backends.py --all  或  install_backends.py anysearch tavily")
        sys.exit(1)
    install(names, a.skills_root, a.dry_run, a.force, a.interactive)


if __name__ == "__main__":
    main()
