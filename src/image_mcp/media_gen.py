"""Standalone generation through an OpenAI compatible Images API."""
from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .errors import MediaError
from .images import MAX_BYTES, decode_image, download_image, encode_png, load_ref
from .styles import STYLE_HINTS, wrap_prompt

RATIO_TO_SIZE = {
    "1:1": "1024x1024",
    "9:16": "1024x1536", "2:3": "1024x1536", "3:4": "1024x1536",
    "16:9": "1536x1024", "3:2": "1536x1024", "4:3": "1536x1024",
}
QUALITIES = ("low", "medium", "high", "auto")
_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-image-2"
    output_dir: Path = Path("./image-mcp-output")

    @classmethod
    def from_env(cls) -> Settings:
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise MediaError("缺少 OPENAI_API_KEY 环境变量")
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
        try:
            parsed = urlsplit(base)
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or parsed.query or parsed.fragment or (parsed.port is not None and parsed.port <= 0)):
                raise ValueError
        except ValueError:
            raise MediaError("OPENAI_BASE_URL 必须是有效的接口地址") from None
        model = os.environ.get("IMAGE_MODEL", "gpt-image-2").strip()
        if not model:
            raise MediaError("IMAGE_MODEL 不能为空")
        output = os.environ.get("IMAGE_MCP_OUTPUT_DIR") or "./image-mcp-output"
        return cls(key, base, model, Path(output).expanduser())


def _extract_image(data: object) -> bytes:
    if not isinstance(data, dict):
        raise MediaError("生图响应格式无效")
    items = data.get("data") or []
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise MediaError("生图响应里没有图片")
    item = items[0]
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded:
        try:
            if len(encoded) > ((MAX_BYTES + 2) // 3) * 4:
                raise MediaError("生成图片超过 20 MB 大小限制")
            return base64.b64decode(encoded, validate=True)
        except MediaError:
            raise
        except Exception:
            raise MediaError("生图响应 base64 无效") from None
    url = item.get("url")
    if isinstance(url, str) and url:
        return download_image(url)
    raise MediaError("生图响应里没有图片")


def call_api(settings: Settings, prompt: str, size: str, quality: str, ref_bytes: bytes | None) -> bytes:
    """One generation POST per call; errors never include provider payloads."""
    endpoint = "/images/edits" if ref_bytes is not None else "/images/generations"
    payload = {"model": settings.model, "prompt": prompt, "n": 1, "quality": quality, "size": size}
    try:
        with requests.Session() as session:
            session.trust_env = False
            kwargs = {"data": payload, "files": {"image": ("ref.png", ref_bytes, "image/png")}} if ref_bytes is not None else {"json": payload}
            with session.post(
                settings.base_url + endpoint, headers={"Authorization": f"Bearer {settings.api_key}"},
                timeout=(10, 180), allow_redirects=False, stream=True, **kwargs,
            ) as response:
                if response.status_code != 200:
                    raise MediaError(f"生图失败 HTTP {response.status_code}")
                # Base64 adds about one third; bound before parsing untrusted JSON.
                max_body = ((MAX_BYTES + 2) // 3) * 4 + 64 * 1024
                raw = bytearray()
                for chunk in response.iter_content(64 * 1024):
                    raw.extend(chunk)
                    if len(raw) > max_body:
                        raise MediaError("生图响应超过大小限制")
                data = json.loads(raw)
        return _extract_image(data)
    except MediaError:
        raise
    except Exception:
        raise MediaError("生图网络失败或响应格式无效") from None


def _build_filename(prompt: str) -> str:
    first = re.split(r"[@#\n。，,;；]", prompt.strip())[0]
    name = _BAD_CHARS.sub("", first).strip()[:20] or "image"
    return f"{time.strftime('%Y%m%d-%H%M%S')}_{name}_{uuid.uuid4().hex[:8]}.png"


def _prepare_output_dir(output_dir: Path) -> Path:
    """Reject known local write failures before downloading or generating."""
    try:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".tmp") as probe:
            probe.write(b"\0")
            probe.flush()
        return output_dir
    except Exception:
        raise MediaError("输出目录不可写，请检查 IMAGE_MCP_OUTPUT_DIR") from None


def save_image(raw: bytes, output_dir: Path, prompt: str) -> tuple[Path, str]:
    """Decode before writing and atomically publish a complete PNG."""
    image = decode_image(raw)
    encoded = encode_png(image)
    temporary = None
    try:
        output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / _build_filename(prompt)
        with tempfile.NamedTemporaryFile(dir=output_dir, suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
        temporary.replace(target)
        return target, f"{image.width}x{image.height}"
    except Exception:
        raise MediaError("图片保存失败，请检查输出目录") from None
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def generate(
    prompt: str, reference_image: str | None = None, aspect_ratio: str = "1:1",
    style: str = "default", quality: str = "low",
) -> dict[str, str]:
    """Generate and return absolute local path, actual size, style and prompt."""
    if not prompt.strip():
        raise MediaError("prompt 不能为空")
    if aspect_ratio not in RATIO_TO_SIZE:
        raise MediaError("不支持的画幅比例")
    if style not in STYLE_HINTS:
        raise MediaError("不支持的风格模板")
    if quality not in QUALITIES:
        raise MediaError("不支持的画质，可选 low、medium、high、auto")
    settings = Settings.from_env()
    final_prompt = wrap_prompt(style, prompt, quality)
    output_dir = _prepare_output_dir(settings.output_dir)
    ref_bytes = load_ref(reference_image) if reference_image is not None else None
    raw = call_api(settings, final_prompt, RATIO_TO_SIZE[aspect_ratio], quality, ref_bytes)
    path, size = save_image(raw, output_dir, prompt)
    return {"path": str(path), "size": size, "style": style, "final_prompt": final_prompt}
