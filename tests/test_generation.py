from __future__ import annotations

import io
import json
import traceback
from contextlib import contextmanager
from pathlib import Path

import pytest
from PIL import Image

from image_mcp.media_gen import MediaError, RATIO_TO_SIZE, Settings, generate
from image_mcp.styles import list_styles, wrap_prompt
from image_mcp.references.search import search_references


def test_environment_defaults(monkeypatch):
    settings = Settings.from_env()
    assert settings.base_url == "https://api.openai.com/v1"
    assert settings.model == "gpt-image-2"
    monkeypatch.delenv("IMAGE_MCP_OUTPUT_DIR")
    assert Settings.from_env().output_dir == Path("./image-mcp-output")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example/v1/")
    monkeypatch.setenv("IMAGE_MODEL", "custom-image")
    assert Settings.from_env().model == "custom-image"
    assert Settings.from_env().base_url == "https://api.example/v1"
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(MediaError, match="OPENAI_API_KEY"):
        Settings.from_env()


def test_styles_and_prompt_preservation():
    styles = list_styles()
    assert len(styles) == 21
    assert len({s["id"] for s in styles}) == 21
    assert all(s["name"] and s["description"] for s in styles)
    raw = "主体：红色机器人；白色背景；标题：明天见\n保留括号（不要裁掉）。"
    final = wrap_prompt("tech_poster", raw, "low")
    assert final.startswith(raw)
    assert "信息层级" in final
    assert "深色调" not in final
    assert "真实摄影" in wrap_prompt("real", "一位老人", "standard")


def test_reference_library_covers_every_style_with_original_text_examples():
    from image_mcp.references.search import load_references
    from image_mcp.styles import STYLE_HINTS
    items = load_references()
    assert len(items) == 21
    assert {item["style"] for item in items} == set(STYLE_HINTS)
    assert len({item["example_prompt"] for item in items}) == 21
    for item in items:
        assert set(item) == {"title", "style", "tags", "example_prompt"}
        assert item["title"] and item["tags"] and item["example_prompt"]
    posters = search_references("海报", 3)
    assert posters
    assert any("海报" in item["title"] or "海报" in item["tags"] for item in posters)
    assert search_references("相机不存在的无关词", 3) == []


def test_search_scoring_and_exact_selection(monkeypatch):
    import image_mcp.references.search as search
    items = [
        {"id": "sample-a", "title": "蓝色海报", "style": "tech_poster", "tags": ["蓝色"], "example_prompt": "蓝色圆形"},
        {"id": "sample-b", "title": "红色花朵", "style": "real", "tags": ["摄影"], "example_prompt": "一朵花"},
    ]
    monkeypatch.setattr(search, "load_references", lambda: items)
    assert search_references("蓝色", 1) == [items[0]]
    assert search_references("sample-b", 1) == [items[1]]
    assert search_references("无关", 3) == []
    assert search_references("", 3) == []
    assert search_references("蓝色", 0) == []


def test_generation_json_and_local_result(backend, monkeypatch):
    url, calls, _ = backend
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MODEL", "test-image")
    result = generate("a blue circle", style="real", aspect_ratio="16:9", quality="low")
    assert Path(result["path"]).is_absolute()
    assert Path(result["path"]).is_file()
    assert result["size"] == "24x12"
    assert result["style"] == "real"
    assert result["final_prompt"].startswith("a blue circle")
    assert "url" not in result
    assert len(calls) == 1
    endpoint, headers, body = calls[0]
    assert endpoint == "/v1/images/generations"
    payload = json.loads(body)
    assert payload == {"model": "test-image", "prompt": result["final_prompt"], "n": 1,
                       "size": "1536x1024", "quality": "low"}
    assert headers["Authorization"] == "Bearer test-only-key"


def test_edits_preserves_reference_frame(backend, monkeypatch, tmp_path, png):
    url, calls, _ = backend
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    ref = tmp_path / "ref.png"
    ref.write_bytes(png)
    result = generate("make it red", reference_image=str(ref))
    endpoint, headers, body = calls[0]
    assert endpoint == "/v1/images/edits"
    assert "multipart/form-data" in headers["Content-Type"]
    assert b'name="quality"\r\n\r\nlow' in body
    assert b'name="image"; filename="ref.png"' in body
    assert Image.open(io.BytesIO(png)).size == (24, 12)
    assert Path(result["path"]).is_file()


@pytest.mark.parametrize("kwargs", [
    {"prompt": " "}, {"prompt": "x", "style": "unknown"},
    {"prompt": "x", "aspect_ratio": "7:9"}, {"prompt": "x", "quality": "unknown"},
])
def test_invalid_arguments_never_call_backend(kwargs, backend, monkeypatch):
    url, calls, _ = backend
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    with pytest.raises(MediaError):
        generate(**kwargs)
    assert calls == []


@pytest.mark.parametrize("status,body", [
    (400, b'test-only-key private-body'), (429, b'test-only-key'),
    (503, b'test-only-key'), (200, b'test-only-key invalid-json'),
    (200, {"data": [{"b64_json": "not valid! test-only-key"}]}),
    (200, {"data": [{"b64_json": "bm90LWFuLWltYWdl"}]}),
    (200, {"data": []}), (200, []), (200, {"data": ["test-only-key"]}),
])
def test_upstream_failures_are_safe_and_not_retried(status, body, backend, monkeypatch):
    url, calls, state = backend
    state.update(status=status, body=body)
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    with pytest.raises(MediaError) as raised:
        generate("test")
    formatted = "".join(traceback.format_exception(raised.value))
    assert "test-only-key" not in formatted
    assert "private-body" not in formatted
    assert len(calls) == 1
    assert not list(Settings.from_env().output_dir.glob("*.png"))


@pytest.mark.parametrize("ratio,size", list(RATIO_TO_SIZE.items()))
def test_ratio_mapping(ratio, size):
    assert size in ("1024x1024", "1024x1536", "1536x1024")


def test_api_timeout_exception_never_discloses_key(monkeypatch):
    import image_mcp.media_gen as module
    import requests
    def fail(*args, **kwargs):
        raise requests.Timeout("Authorization: Bearer test-only-key")
    monkeypatch.setattr(requests.Session, "post", fail)
    with pytest.raises(MediaError) as raised:
        module.generate("test")
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))


def test_upstream_url_materializes_only_as_local_png(backend, monkeypatch, png):
    import image_mcp.media_gen as module
    url, calls, state = backend
    state["body"] = {"data": [{"url": "https://images.example/generated.png"}]}
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    urls = []
    def download(url):
        urls.append(url)
        return png
    monkeypatch.setattr(module, "download_image", download)
    result = module.generate("test")
    assert urls == ["https://images.example/generated.png"]
    assert set(result) == {"path", "size", "style", "final_prompt"}
    assert Path(result["path"]).is_file()
    assert len(calls) == 1


def test_settings_repr_and_invalid_url_do_not_disclose_key(monkeypatch):
    assert "test-only-key" not in repr(Settings.from_env())
    monkeypatch.setenv("OPENAI_BASE_URL", "https://user:test-only-key@api.example/v1")
    with pytest.raises(MediaError) as raised:
        Settings.from_env()
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))


def test_save_failure_has_no_partial_file_or_secret_path(tmp_path, monkeypatch, png):
    from image_mcp.media_gen import save_image
    def fail(*args, **kwargs):
        raise OSError("test-only-key")
    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(MediaError) as raised:
        save_image(png, tmp_path, "test")
    assert "test-only-key" not in "".join(traceback.format_exception(raised.value))
    assert list(tmp_path.iterdir()) == []


def test_temporary_cleanup_error_does_not_expose_secret(tmp_path, monkeypatch, png):
    from image_mcp.media_gen import save_image
    original_unlink = Path.unlink
    def fail(self, *args, **kwargs):
        if self.suffix == ".tmp":
            raise OSError("test-only-key")
        return original_unlink(self, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail)
    path, _ = save_image(png, tmp_path, "test")
    assert path.is_file()


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("reference", [None, "https://images.example/reference.png"])
def test_invalid_output_directory_stops_before_network(
    tmp_path, monkeypatch, backend, png, nested, reference,
):
    import image_mcp.images as images
    url, calls, _ = backend
    blocked = tmp_path / "existing-file"
    blocked.write_text("keep this file")
    output = blocked / "output" if nested else blocked
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(output))
    downloads = []

    def download(value):
        downloads.append(value)
        return png

    monkeypatch.setattr(images, "download_image", download)
    with pytest.raises(MediaError, match="输出目录"):
        generate("test", reference_image=reference)
    assert downloads == []
    assert calls == []
    assert blocked.read_text() == "keep this file"


def test_unwritable_output_directory_stops_before_network(tmp_path, monkeypatch, backend, png):
    import image_mcp.images as images
    import image_mcp.media_gen as module
    url, calls, _ = backend
    output = tmp_path / "output"
    output.mkdir()
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(output))
    downloads = []

    def fail(*args, **kwargs):
        raise PermissionError("private-directory-detail")

    def download(value):
        downloads.append(value)
        return png

    monkeypatch.setattr(module.tempfile, "NamedTemporaryFile", fail)
    monkeypatch.setattr(images, "download_image", download)
    with pytest.raises(MediaError, match="输出目录") as raised:
        generate("test", reference_image="https://images.example/reference.png")
    assert downloads == []
    assert calls == []
    assert list(output.iterdir()) == []
    assert "private-directory-detail" not in "".join(traceback.format_exception(raised.value))


@pytest.mark.parametrize("existing", [False, True])
def test_output_directory_is_ready_and_probe_removed_before_network(
    tmp_path, monkeypatch, backend, png, existing,
):
    import image_mcp.images as images
    url, calls, _ = backend
    output = tmp_path / "images" / "output"
    if existing:
        output.mkdir(parents=True)
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(output))

    def download(value):
        assert output.is_dir()
        assert list(output.iterdir()) == []
        return png

    monkeypatch.setattr(images, "download_image", download)
    result = generate("test", reference_image="https://images.example/reference.png")
    assert len(calls) == 1
    assert Path(result["path"]).is_absolute()
    assert Path(result["path"]).parent == output.resolve()
    assert list(output.iterdir()) == [Path(result["path"])]


def test_output_probe_write_failure_cleans_up_before_network(tmp_path, monkeypatch, backend):
    import image_mcp.media_gen as module
    url, calls, _ = backend
    output = tmp_path / "output"
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(output))
    temporary_file = module.tempfile.NamedTemporaryFile

    @contextmanager
    def failing_probe(*args, **kwargs):
        with temporary_file(*args, **kwargs) as stream:
            def fail(value):
                raise OSError("private-write-failure")
            monkeypatch.setattr(stream, "write", fail)
            yield stream

    monkeypatch.setattr(module.tempfile, "NamedTemporaryFile", failing_probe)
    with pytest.raises(MediaError, match="输出目录") as raised:
        generate("test")
    assert calls == []
    assert list(output.iterdir()) == []
    assert "private-write-failure" not in "".join(traceback.format_exception(raised.value))


def test_output_directory_changed_after_request_still_reports_save_failure(
    tmp_path, monkeypatch, backend,
):
    import image_mcp.media_gen as module
    url, calls, _ = backend
    output = tmp_path / "output"
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(output))
    call_api = module.call_api

    def changed_directory(*args, **kwargs):
        raw = call_api(*args, **kwargs)
        output.rmdir()
        output.write_text("another process created this file")
        return raw

    monkeypatch.setattr(module, "call_api", changed_directory)
    with pytest.raises(MediaError, match="图片保存失败"):
        generate("test")
    assert len(calls) == 1
    assert output.read_text() == "another process created this file"
    assert list(tmp_path.iterdir()) == [output]
