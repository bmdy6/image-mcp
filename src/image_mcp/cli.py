"""Command-line entry point."""
from __future__ import annotations

import argparse
import json
import sys

from .errors import MediaError
from .media_gen import QUALITIES, RATIO_TO_SIZE, generate
from .references.search import search_references
from .styles import STYLE_HINTS, list_styles


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenAI 兼容接口的本地生图工具")
    commands = parser.add_subparsers(dest="command", required=True)
    generate_cmd = commands.add_parser("generate", help="文生图或图生图")
    generate_cmd.add_argument("prompt")
    generate_cmd.add_argument("--style", choices=list(STYLE_HINTS), default="default")
    generate_cmd.add_argument("--ratio", choices=list(RATIO_TO_SIZE), default="1:1")
    generate_cmd.add_argument("--quality", choices=QUALITIES, default="low")
    generate_cmd.add_argument("--ref", action="append", help="本地图片路径或公网 HTTPS 链接，可按顺序重复")
    commands.add_parser("styles", help="列出中文风格模板")
    search_cmd = commands.add_parser("search", help="检索本地参考案例")
    search_cmd.add_argument("query")
    search_cmd.add_argument("--limit", type=int, default=3)
    commands.add_parser("mcp", help="启动 stdio MCP 服务")
    args = parser.parse_args()
    try:
        if args.command == "mcp":
            from .server import run
            run()
            return 0
        if args.command == "generate":
            data = generate(args.prompt, aspect_ratio=args.ratio, style=args.style, quality=args.quality,
                            reference_images=args.ref)
        elif args.command == "styles":
            data = list_styles()
        else:
            data = search_references(args.query, args.limit)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    except MediaError as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
