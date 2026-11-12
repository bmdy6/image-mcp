"""Compose a character pose edit from local reference images."""
from __future__ import annotations

from pathlib import Path

from .errors import MediaError
from .images import EXTENSIONS


def _local_image(value: str, role: str) -> str:
    try:
        path = Path(value).expanduser().resolve(strict=True)
        if path.suffix.lower() in EXTENSIONS and path.is_file():
            return str(path)
    except (OSError, RuntimeError, ValueError):
        pass
    raise MediaError(f"{role}必须是存在的本地 PNG、JPEG、WebP 或 GIF 文件")


def prepare_pose(
    character_image: str, pose_image: str, outfit_image: str | None = None,
    extra_prompt: str = "",
) -> dict[str, str | list[str]]:
    references = [_local_image(character_image, "角色参考图")]
    roles = ["第 1 张是角色参考。"]
    if outfit_image is not None:
        references.append(_local_image(outfit_image, "服装参考图"))
        roles.append("第 2 张是服装参考。")
        outfit = "按服装参考更换衣物，保留角色的脸、发型或头部造型及其他身份特征。"
    else:
        outfit = "保留角色的脸、发型或头部造型、配色、服装和配饰。"
    references.append(_local_image(pose_image, "姿势参考图"))
    roles.append(f"第 {len(references)} 张是姿势参考。")
    lines = [
        "根据参考图重绘同一个角色。" + "".join(roles),
        outfit,
        "只从姿势图提取身体姿势、重心、四肢位置和镜头角度。成图里不要出现线稿、骨架或辅助线。",
    ]
    if extra_prompt.strip():
        lines.append(f"画面补充：{extra_prompt.strip()}")
    return {"prompt": "\n".join(lines), "reference_images": references}
