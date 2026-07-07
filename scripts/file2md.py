#!/usr/bin/env python3
"""文件转 Markdown 薄封装（基于 microsoft/markitdown）。

用法：
  python3 file2md.py <path> [--out out.md]

供场景 C（material-manager.py）调用：把 PDF/DOCX/PPTX/XLSX/EPUB/HTML/CSV/
JSON/XML/音频等本地文件转成「保留结构的」Markdown，再喂给 LLM 分析。
markitdown 缺失时 file_to_markdown() 返回 None，调用方自行降级——与搜索后端
「缺失就跳过」同一套路，不抛异常、不阻断流程。

注意：只启用 markitdown 内置转换器（enable_plugins=False），不引 openai /
不调用 LLM 做图片/音频描述（那部分由本 skill 的 common.llm 在 analyze_image
里统一处理），避免依赖冲突与额外计费。
"""
from __future__ import annotations

import argparse
import os
import sys


def is_available() -> bool:
    """markitdown 是否已可导入。"""
    try:
        import markitdown  # noqa: F401
        return True
    except Exception:
        return False


def file_to_markdown(path: str) -> str | None:
    """把文件转成 Markdown 文本；失败/未安装/为空返回 None。

    支持：PDF, DOCX, PPTX, XLSX, EPUB, HTML, CSV, JSON, XML, TXT, MD,
    以及图片(EXIF/OCR)、音频(EXIF/转写)等 markitdown 识别的格式。
    """
    if not os.path.isfile(path):
        return None
    if not is_available():
        return None
    try:
        from markitdown import MarkItDown

        md = MarkItDown(enable_plugins=False)
        result = md.convert(path)
        text = getattr(result, "text_content", None)
        return text or None
    except Exception as e:  # noqa: BLE001
        print(f"[file2md] 转换失败: {e}", file=sys.stderr)
        return None


def main() -> None:
    p = argparse.ArgumentParser(description="文件转 Markdown（markitdown）")
    p.add_argument("path", help="待转换文件")
    p.add_argument("--out", help="输出 .md 路径（默认打印到 stdout）")
    args = p.parse_args()

    if not is_available():
        print(
            "[file2md] 未安装 markitdown，请执行: pip install 'markitdown[all]'",
            file=sys.stderr,
        )
        sys.exit(2)

    text = file_to_markdown(args.path)
    if text is None:
        print(f"[file2md] 转换失败或结果为空: {args.path}", file=sys.stderr)
        sys.exit(1)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"[file2md] 已写出: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
