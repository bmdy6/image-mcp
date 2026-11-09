"""Three stdio MCP tools for local image generation and discovery."""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .media_gen import generate
from .references.search import search_references
from .styles import list_styles as style_catalog

mcp = FastMCP("image-mcp", instructions="使用 OpenAI 兼容接口生成图片并保存到本地。", log_level="WARNING")


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True,
                                      destructiveHint=False, idempotentHint=False))
def generate_image(
    prompt: str, reference_image: str | None = None, aspect_ratio: str = "1:1",
    style: str = "default", quality: str = "low",
) -> str:
    """文生图或图生图，返回本地绝对路径、实际尺寸、风格和最终提示词。

    reference_image 接受本地图片或公网 HTTPS 图片；画幅支持 1:1、9:16、2:3、
    3:4、16:9、3:2、4:3；quality 支持 low、medium、high、auto。
    """
    return json.dumps(generate(prompt, reference_image, aspect_ratio, style, quality), ensure_ascii=False)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def list_styles() -> str:
    """列出 21 种模板的 id、中文名和一句说明。"""
    return json.dumps(style_catalog(), ensure_ascii=False)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def search_reference_images(query: str, limit: int = 3) -> str:
    """检索本地参考案例的标题、风格、标签和示例提示词；无匹配时返回空列表。"""
    return json.dumps(search_references(query, limit), ensure_ascii=False)


def run() -> None:
    mcp.run(transport="stdio")
