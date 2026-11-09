"""Bounded local image decoding and public HTTPS downloads."""
from __future__ import annotations

import io
import ipaddress
import os
import socket
import ssl
import warnings
from contextlib import suppress
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import urllib3
from PIL import Image, ImageOps

from .errors import MediaError

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_EDGE = 8192
MAX_REDIRECTS = 5
_FAKE_IP_NETWORK = ipaddress.ip_network("198.18.0.0/15")
FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp", "GIF": "image/gif"}
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def decode_image(raw: bytes) -> Image.Image:
    """Validate format and decoding budget, orient, and return detached pixels."""
    if len(raw) > MAX_BYTES:
        raise MediaError("图片超过 20 MB 大小限制")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as opened:
                if opened.format not in FORMATS or getattr(opened, "is_animated", False):
                    raise MediaError("仅支持静态 PNG、JPEG、WebP 或 GIF 图片")
                width, height = opened.size
                if width * height > MAX_PIXELS or max(width, height) > MAX_EDGE:
                    raise MediaError("图片解码尺寸超过限制")
                return ImageOps.exif_transpose(opened).convert("RGBA")
    except MediaError:
        raise
    except Exception:
        raise MediaError("图片不是有效且受支持的图片") from None


def encode_png(image: Image.Image) -> bytes:
    try:
        buf = io.BytesIO()
        image.save(buf, "PNG")
        result = buf.getvalue()
    except Exception:
        raise MediaError("图片编码失败") from None
    if len(result) > MAX_BYTES:
        raise MediaError("规范化后的图片超过 20 MB 大小限制")
    return result


def download_image(url: str) -> bytes:
    """Follow at most five HTTPS redirects, validating and pinning every hop."""
    for _ in range(MAX_REDIRECTS + 1):
        result = _download_image_hop(url)
        if isinstance(result, bytes):
            return result
        url = result
    raise MediaError("图片下载重定向次数超过限制")


def _download_image_hop(url: str) -> bytes | str:
    """Return image bytes or a redirect target; never delegate redirects.

    IMAGE_MCP_ALLOW_FAKE_IP=1 permits only the proxy fake-IP range in addition
    to public IPs. Original-host TLS verification and IP pinning still apply.
    Proxy environment variables are not used.
    """
    pool = None
    response = None
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment):
            raise MediaError("图片链接必须是不含凭据的公网 HTTPS 地址")
        host = parsed.hostname.encode("idna").decode("ascii")
        port = parsed.port or 443
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
        if not addresses:
            raise MediaError("图片地址无法解析")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.version == 4 and ip in _FAKE_IP_NETWORK:
                if os.environ.get("IMAGE_MCP_ALLOW_FAKE_IP") != "1":
                    raise MediaError(
                        "目标域名解析到 198.18.0.0/15，常见于代理软件的 fake-ip 模式；"
                        "确认是代理造成的，可以设置 IMAGE_MCP_ALLOW_FAKE_IP=1"
                    )
                continue
            mapped = getattr(ip, "ipv4_mapped", None)
            if not ip.is_global or (mapped is not None and not mapped.is_global):
                raise MediaError("图片链接不能指向本地或私有网络地址")
        pool = urllib3.HTTPSConnectionPool(
            sorted(addresses)[0], port=port, server_hostname=host, assert_hostname=host,
            cert_reqs=ssl.CERT_REQUIRED, timeout=urllib3.Timeout(connect=10, read=30),
        )
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        authority = f"[{host}]" if ":" in host else host
        if port != 443:
            authority += f":{port}"
        response = pool.urlopen(
            "GET", target, headers={"Host": authority, "Accept-Encoding": "identity"},
            redirect=False, retries=False, preload_content=False,
        )
        if response.status in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                raise MediaError("图片重定向缺少目标地址")
            return urljoin(url, location)
        if response.status != 200:
            raise MediaError(f"图片下载失败 HTTP {response.status}")
        mime = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if mime not in FORMATS.values():
            raise MediaError("图片响应类型不受支持")
        declared = response.headers.get("Content-Length")
        if declared is not None and (int(declared) < 0 or int(declared) > MAX_BYTES):
            raise MediaError("图片超过 20 MB 大小限制")
        raw = bytearray()
        for chunk in response.stream(64 * 1024, decode_content=True):
            raw.extend(chunk)
            if len(raw) > MAX_BYTES:
                raise MediaError("图片超过 20 MB 大小限制")
        result = bytes(raw)
        decode_image(result)
        with Image.open(io.BytesIO(result)) as opened:
            if FORMATS[opened.format] != mime:
                raise MediaError("图片响应类型与文件内容不一致")
        return result
    except MediaError:
        raise
    except Exception:
        raise MediaError("图片下载失败或地址无效") from None
    finally:
        if response is not None:
            with suppress(Exception):
                response.close()
        if pool is not None:
            with suppress(Exception):
                pool.close()


def load_ref(path_or_url: str) -> bytes:
    """Read a regular image file or public HTTPS image; preserve full frame."""
    try:
        if "://" in path_or_url or path_or_url.lower().startswith(("https:", "http:", "data:", "file:")):
            raw = download_image(path_or_url)
        else:
            path = Path(path_or_url).expanduser()
            if path.suffix.lower() not in EXTENSIONS or not path.is_file():
                raise MediaError("本地参考图必须是受支持的图片文件")
            with path.open("rb") as source:
                raw = source.read(MAX_BYTES + 1)
        image = decode_image(raw)
        if max(image.size) > 2048:
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        return encode_png(image)
    except MediaError:
        raise
    except Exception:
        raise MediaError("参考图读取失败") from None
