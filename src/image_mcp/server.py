"""Stdio MCP tools for local image generation and discovery."""
from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .media_gen import generate
from .pose import prepare_pose
from .references.search import search_references
from .styles import list_styles as style_catalog

mcp = FastMCP(
    "image-mcp",
    instructions=(
        "文生图或图生图可用 generate_image，使用已配置的 API Key 计费。"
        "角色换姿势或换装时，先用 prepare_pose_image 整理提示词和参考图。"
        "如果用户没有指定后端，且当前 Codex 会话有内置生图工具，优先用内置工具出图。"
        "只有用户明确选择 API 出图时，才将准备结果传给 generate_image。"
    ),
    log_level="WARNING",
)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True,
                                      destructiveHint=False, idempotentHint=False))
def generate_image(
    prompt: str, reference_image: str | None = None, aspect_ratio: str = "1:1",
    style: str = "default", quality: str = "low", reference_images: list[str] | None = None,
) -> str:
    """使用已配置的 API Key 生成或编辑图片，返回本地 PNG 路径、尺寸和提示词。

    单张图用 reference_image，多张用 reference_images（按提示词顺序，1 至 4 张）。
    每张图接受本地路径或公网 HTTPS 链接；画幅支持 1:1、9:16、2:3、
    3:4、16:9、3:2、4:3；quality 支持 low、medium、high、auto。
    """
    result = generate(prompt, reference_image, aspect_ratio, style, quality, reference_images=reference_images)
    return json.dumps(result, ensure_ascii=False)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
def prepare_pose_image(
    character_image: str, pose_image: str, outfit_image: str | None = None,
    extra_prompt: str = "",
) -> str:
    """准备角色换姿势或换装的提示词及有序参考图，无需 API Key。

    参考图填写本地图片路径。先用 Codex 内置生图（如果可用），按返回顺序附图。
    用户明确选择 API 出图后，可以将返回的 prompt 和 reference_images 传给 generate_image。
    """
    return json.dumps(prepare_pose(character_image, pose_image, outfit_image, extra_prompt), ensure_ascii=False)


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
