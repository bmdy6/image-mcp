from __future__ import annotations

import io
import ipaddress
import socket
import traceback
from unittest.mock import MagicMock

import pytest
from PIL import Image

from image_mcp import images
from image_mcp.media_gen import MediaError


@pytest.mark.parametrize("url", [
    "http://8.8.8.8/a.png", "file:///etc/hosts", "ftp://example.com/a.png",
    "https://127.0.0.1/a.png", "https://10.0.0.1/a.png", "https://169.254.169.254/a.png",
    "https://[::1]/a.png", "https://[fe80::1]/a.png", "https://[::ffff:127.0.0.1]/a.png",
    "https://user:test-only-key@example.com/a.png", "https:///a.png", "https://example.com:bad/a.png",
])
def test_unsafe_urls_rejected_before_download(url, monkeypatch):
    pool = MagicMock()
    monkeypatch.setattr(images.urllib3, "HTTPSConnectionPool", pool)
    with pytest.raises(MediaError):
        images.download_image(url)
    pool.assert_not_called()


@pytest.mark.parametrize("addresses", [[], ["8.8.8.8", "10.0.0.1"], ["192.168.1.1"], ["100.64.0.1"]])
def test_dns_fails_closed_for_any_nonpublic_address(addresses, monkeypatch):
    monkeypatch.setattr(images.socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses])
    with pytest.raises(MediaError):
        images.download_image("https://images.example/test.png")


def remote(monkeypatch, png, *, status=200, headers=None, chunks=None):
    def resolve(host, *args, **kwargs):
        try:
            address = str(ipaddress.ip_address(host))
        except ValueError:
            address = "8.8.8.8"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    monkeypatch.setattr(images.socket, "getaddrinfo", resolve)
    response = MagicMock(status=status, headers=headers or {"Content-Type": "image/png"})
    response.stream.return_value = iter(chunks if chunks is not None else [png])
    pool = MagicMock()
    pool.urlopen.return_value = response
    factory = MagicMock(return_value=pool)
    monkeypatch.setattr(images.urllib3, "HTTPSConnectionPool", factory)
    return response, pool, factory


def test_public_download_pins_ip_and_verifies_original_tls_host(monkeypatch, png):
    response, pool, factory = remote(monkeypatch, png)
    assert images.download_image("https://images.example/a.png?q=1") == png
    assert factory.call_args.args[0] == "8.8.8.8"
    assert factory.call_args.kwargs["assert_hostname"] == "images.example"
    assert factory.call_args.kwargs["server_hostname"] == "images.example"
    assert pool.urlopen.call_args.kwargs["redirect"] is False
    assert pool.urlopen.call_args.kwargs["retries"] is False
    assert pool.urlopen.call_args.kwargs["headers"]["Host"] == "images.example"
    response.close.assert_called_once()
    pool.close.assert_called_once()


@pytest.mark.parametrize("status,headers,chunks", [
    (302, {"Location": "https://127.0.0.1/a.png"}, []),
    (200, {"Content-Type": "text/html"}, [b"bad"]),
    (200, {"Content-Type": "image/svg+xml"}, [b"<svg/>"]),
    (200, {"Content-Type": "image/png", "Content-Length": "20971521"}, []),
    (200, {"Content-Type": "image/png", "Content-Length": "bad"}, []),
    (200, {"Content-Type": "image/png"}, [b"x" * (20 * 1024 * 1024 + 1)]),
    (200, {"Content-Type": "image/png"}, [b"not an image"]),
])
def test_download_rejects_redirect_type_and_size_and_closes(status, headers, chunks, monkeypatch, png):
    response, pool, _ = remote(monkeypatch, png, status=status, headers=headers, chunks=chunks)
    with pytest.raises(MediaError):
        images.download_image("https://images.example/a.png")
    response.close.assert_called_once()
    pool.close.assert_called_once()


def test_mime_must_match_decoded_image(monkeypatch, png):
    remote(monkeypatch, png, headers={"Content-Type": "image/jpeg"})
    with pytest.raises(MediaError):
        images.download_image("https://images.example/a.jpg")


def test_local_images_validate_bytes_and_preserve_frame(tmp_path, png):
    ref = tmp_path / "ref.png"
    ref.write_bytes(png)
    result = images.load_ref(str(ref))
    assert Image.open(io.BytesIO(result)).size == (24, 12)
    ref.write_bytes(b"not an image")
    with pytest.raises(MediaError):
        images.load_ref(str(ref))
    with pytest.raises(MediaError):
        images.load_ref(str(tmp_path))
    secret = tmp_path / "test-only-key.txt"
    secret.write_bytes(png)
    with pytest.raises(MediaError) as raised:
        images.load_ref(str(secret))
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))


def test_exif_orientation_is_applied(tmp_path):
    ref = tmp_path / "oriented.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 20), "red").save(ref, exif=exif)
    prepared = images.load_ref(str(ref))
    assert Image.open(io.BytesIO(prepared)).size == (20, 40)


def test_local_reference_size_limit(tmp_path, monkeypatch, png):
    ref = tmp_path / "ref.png"
    ref.write_bytes(png)
    monkeypatch.setattr(images, "MAX_BYTES", 4)
    with pytest.raises(MediaError):
        images.load_ref(str(ref))


def test_reference_pixel_budget_is_checked_before_conversion(monkeypatch, png):
    monkeypatch.setattr(images, "MAX_PIXELS", 10)
    with pytest.raises(MediaError, match="尺寸"):
        images.decode_image(png)


def test_animated_reference_is_rejected(tmp_path):
    ref = tmp_path / "moving.gif"
    Image.new("RGB", (8, 8), "red").save(ref, save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")], duration=100, loop=0)
    with pytest.raises(MediaError, match="静态"):
        images.load_ref(str(ref))


def test_dns_error_has_no_untrusted_exception_context(monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("test-only-key")
    monkeypatch.setattr(images.socket, "getaddrinfo", fail)
    with pytest.raises(MediaError) as raised:
        images.download_image("https://images.example/a.png")
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))


def test_download_closes_on_stream_failure(monkeypatch, png):
    response, pool, _ = remote(monkeypatch, png)
    response.stream.side_effect = OSError("test-only-key")
    with pytest.raises(MediaError) as raised:
        images.download_image("https://images.example/a.png")
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))
    response.close.assert_called_once()
    pool.close.assert_called_once()


def test_cleanup_failure_never_exposes_url_or_masks_valid_image(monkeypatch, png):
    response, pool, _ = remote(monkeypatch, png)
    response.close.side_effect = OSError("test-only-key")
    pool.close.side_effect = OSError("test-only-key")
    assert images.download_image("https://images.example/a.png") == png
    pool.close.assert_called_once()


def test_png_encoding_failure_is_safe(monkeypatch, png):
    image = images.decode_image(png)
    def fail(*args, **kwargs):
        raise OSError("test-only-key")
    monkeypatch.setattr(image, "save", fail)
    with pytest.raises(MediaError) as raised:
        images.encode_png(image)
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))


@pytest.mark.parametrize("address", ["198.18.0.1", "198.19.255.254"])
@pytest.mark.parametrize("value", [None, "0", "true", "yes"])
def test_fake_ip_requires_explicit_opt_in(address, value, monkeypatch, png):
    _, _, factory = remote(monkeypatch, png)
    monkeypatch.setattr(images.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    if value is not None:
        monkeypatch.setenv("IMAGE_MCP_ALLOW_FAKE_IP", value)
    with pytest.raises(MediaError) as raised:
        images.download_image("https://images.example/a.png")
    message = str(raised.value)
    assert "目标域名解析到 198.18.0.0/15" in message
    assert "fake-ip" in message
    assert "IMAGE_MCP_ALLOW_FAKE_IP=1" in message
    factory.assert_not_called()


@pytest.mark.parametrize("address", ["198.18.0.1", "198.19.255.254"])
def test_fake_ip_opt_in_preserves_ip_pinning_and_tls(address, monkeypatch, png):
    response, pool, factory = remote(monkeypatch, png)
    monkeypatch.setenv("IMAGE_MCP_ALLOW_FAKE_IP", "1")
    monkeypatch.setattr(images.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    assert images.download_image("https://images.example/a.png") == png
    assert factory.call_args.args[0] == address
    assert factory.call_args.kwargs["assert_hostname"] == "images.example"
    response.close.assert_called_once()
    pool.close.assert_called_once()


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "100.64.0.1",
    "::1", "fe80::1", "::ffff:127.0.0.1",
])
def test_fake_ip_opt_in_never_allows_other_nonpublic_addresses(address, monkeypatch, png):
    _, _, factory = remote(monkeypatch, png)
    monkeypatch.setenv("IMAGE_MCP_ALLOW_FAKE_IP", "1")
    monkeypatch.setattr(images.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    with pytest.raises(MediaError):
        images.download_image("https://images.example/a.png")
    factory.assert_not_called()


def redirect_chain(monkeypatch, png, locations, addresses):
    def resolve(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses[host]]
    monkeypatch.setattr(images.socket, "getaddrinfo", resolve)
    responses = [MagicMock(status=302, headers={"Location": url}) for url in locations]
    final = MagicMock(status=200, headers={"Content-Type": "image/png"})
    final.stream.return_value = iter([png])
    responses.append(final)
    pools = [MagicMock() for _ in responses]
    for pool, response in zip(pools, responses):
        pool.urlopen.return_value = response
    factory = MagicMock(side_effect=pools)
    monkeypatch.setattr(images.urllib3, "HTTPSConnectionPool", factory)
    return responses, pools, factory


def test_public_redirect_checks_and_pins_each_hop(monkeypatch, png):
    responses, pools, factory = redirect_chain(monkeypatch, png,
        ["https://cdn.example/b.png", "/final.png"],
        {"images.example": ["8.8.8.8"], "cdn.example": ["1.1.1.1"]})
    assert images.download_image("https://images.example/a.png") == png
    assert [call.args[0] for call in factory.call_args_list] == ["8.8.8.8", "1.1.1.1", "1.1.1.1"]
    assert pools[-1].urlopen.call_args.args[1] == "/final.png"
    for response, pool in zip(responses, pools):
        response.close.assert_called_once()
        pool.close.assert_called_once()
        assert pool.urlopen.call_args.kwargs["redirect"] is False


@pytest.mark.parametrize("opt_in", [False, True])
def test_redirect_fake_ip_uses_same_policy(opt_in, monkeypatch, png):
    responses, pools, factory = redirect_chain(monkeypatch, png,
        ["https://cdn.example/b.png"],
        {"images.example": ["8.8.8.8"], "cdn.example": ["198.18.0.2"]})
    if opt_in:
        monkeypatch.setenv("IMAGE_MCP_ALLOW_FAKE_IP", "1")
        assert images.download_image("https://images.example/a.png") == png
        assert factory.call_count == 2
        responses[1].close.assert_called_once()
    else:
        with pytest.raises(MediaError, match="IMAGE_MCP_ALLOW_FAKE_IP=1"):
            images.download_image("https://images.example/a.png")
        assert factory.call_count == 1
    responses[0].close.assert_called_once()
    pools[0].close.assert_called_once()


@pytest.mark.parametrize("addresses", [["127.0.0.1"], ["10.0.0.1"], ["169.254.169.254"], ["198.18.0.1", "10.0.0.1"]])
def test_redirect_private_target_blocked_even_with_fake_ip_opt_in(addresses, monkeypatch, png):
    responses, pools, factory = redirect_chain(monkeypatch, png,
        ["https://cdn.example/b.png"],
        {"images.example": ["8.8.8.8"], "cdn.example": addresses})
    monkeypatch.setenv("IMAGE_MCP_ALLOW_FAKE_IP", "1")
    with pytest.raises(MediaError):
        images.download_image("https://images.example/a.png")
    assert factory.call_count == 1
    responses[0].close.assert_called_once()
    pools[0].close.assert_called_once()


@pytest.mark.parametrize("target", ["http://cdn.example/a.png", "file:///etc/hosts", "https://user:secret@cdn.example/a.png"])
def test_redirect_rejects_unsafe_scheme_or_credentials(target, monkeypatch, png):
    responses, pools, factory = redirect_chain(monkeypatch, png, [target], {"images.example": ["8.8.8.8"]})
    with pytest.raises(MediaError):
        images.download_image("https://images.example/a.png")
    assert factory.call_count == 1
    responses[0].close.assert_called_once()


def test_redirect_loop_is_bounded(monkeypatch, png):
    responses, pools, factory = redirect_chain(monkeypatch, png, ["/a.png"] * 6, {"images.example": ["8.8.8.8"]})
    with pytest.raises(MediaError, match="重定向次数"):
        images.download_image("https://images.example/a.png")
    assert factory.call_count == 6
    for response, pool in zip(responses[:6], pools[:6]):
        response.close.assert_called_once()
        pool.close.assert_called_once()


@pytest.mark.parametrize("address", ["198.17.255.255", "198.20.0.0"])
def test_public_addresses_outside_fake_ip_range_keep_existing_policy(address, monkeypatch, png):
    _, _, factory = remote(monkeypatch, png)
    monkeypatch.setattr(images.socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    assert ipaddress.ip_address(address).is_global
    assert images.download_image("https://images.example/a.png") == png
    assert factory.call_args.args[0] == address
