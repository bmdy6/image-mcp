"""Prompt composition using optional style hints from media resources."""
from __future__ import annotations

import json
from pathlib import Path


STYLE_HINTS_PATH = Path(__file__).resolve().parent / "prompts" / "style_hints.json"
STYLE_HINTS: dict[str, str] = json.loads(STYLE_HINTS_PATH.read_text(encoding="utf-8"))
QUALITY_HINTS_PATH = Path(__file__).resolve().parent / "prompts" / "quality_hints.json"
QUALITY_HINTS: dict[str, str] = json.loads(QUALITY_HINTS_PATH.read_text(encoding="utf-8"))


def wrap_prompt(style_id: str, raw_prompt: str, quality: str) -> str:
    """Keep the complete user prompt intact and append nonbinding hints."""
    parts = [raw_prompt]
    style_hint = STYLE_HINTS.get(style_id)
    if style_hint:
        parts.append(style_hint)

    quality_hint = QUALITY_HINTS.get(quality)
    if quality_hint:
        parts.append(quality_hint)

    return "\n\n".join(parts)


STYLE_NAMES = {
    "default": "默认", "real": "真实摄影", "product": "商业产品",
    "tech_poster": "科技海报", "travel": "旅行杂志", "travel_guide": "旅行手账",
    "interior": "室内空间", "live_stream": "直播界面", "silhouette": "叙事剪影",
    "silk_road": "丝路绘画", "vintage_5s": "复古胶片", "ccd_snap": "日常抓拍",
    "relation_map": "关系图谱", "encyclopedia": "百科图鉴", "restore_old": "旧照修复",
    "ui_upgrade": "界面重绘", "knowledge_card": "知识卡片", "product_detail": "商品详情",
    "app_ui_design": "应用界面", "campaign_poster": "活动海报", "virtual_tryon": "虚拟试衣",
}


def list_styles() -> list[dict[str, str]]:
    """返回模板 id、中文名和一句说明。"""
    return [
        {"id": key, "name": STYLE_NAMES[key], "description": hint.split("。")[0] + "。"}
        for key, hint in STYLE_HINTS.items()
    ]
