from __future__ import annotations

import asyncio
import json
import os
import sys
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.fixture(autouse=True)
def without_console_script_on_path(monkeypatch):
    monkeypatch.setenv("PATH", "")


def run_cli(*args, env=None):
    return subprocess.run([sys.executable, "-m", "image_mcp", *args], env=env or os.environ.copy(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)


def test_metadata_cli_needs_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    styles = run_cli("styles")
    assert styles.returncode == 0, styles.stderr
    assert len(json.loads(styles.stdout)) == 21
    result = run_cli("search", "科技海报")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)


def test_cli_generation_and_edit(backend, monkeypatch):
    url, calls, _ = backend
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    generated = run_cli("generate", "a blue circle", "--quality", "low", "--ratio", "3:4", "--style", "real")
    assert generated.returncode == 0, generated.stderr
    path = json.loads(generated.stdout)["path"]
    edited = run_cli("generate", "make it red", "--ref", path, "--quality", "low")
    assert edited.returncode == 0, edited.stderr
    assert Path(json.loads(edited.stdout)["path"]).is_file()
    assert [call[0] for call in calls] == ["/v1/images/generations", "/v1/images/edits"]


def test_cli_error_never_exposes_provider_key(backend, monkeypatch):
    url, _, state = backend
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    state.update(status=503, body=b"test-only-key")
    result = run_cli("generate", "test", "--quality", "low")
    assert result.returncode == 1
    assert "HTTP 503" in result.stderr
    assert "test-only-key" not in result.stderr + result.stdout


def test_cli_invalid_output_directory_never_calls_provider(backend, monkeypatch, tmp_path):
    url, calls, _ = backend
    output = tmp_path / "existing-file"
    output.write_text("keep this file")
    monkeypatch.setenv("OPENAI_BASE_URL", url)
    monkeypatch.setenv("IMAGE_MCP_OUTPUT_DIR", str(output))
    result = run_cli("generate", "test", "--quality", "low")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "输出目录不可写" in result.stderr
    assert calls == []
    assert output.read_text() == "keep this file"


def test_sdk_stdio_tools_annotations_and_fake_generation(backend, monkeypatch):
    url, calls, _ = backend
    monkeypatch.setenv("OPENAI_BASE_URL", url)

    async def check():
        params = StdioServerParameters(command=sys.executable, args=["-m", "image_mcp", "mcp"], env=os.environ.copy())
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=15)) as session:
                await session.initialize()
                listing = await session.list_tools()
                tools = {tool.name: tool for tool in listing.tools}
                assert set(tools) == {"generate_image", "list_styles", "search_reference_images"}
                assert tools["generate_image"].annotations.readOnlyHint is False
                assert tools["generate_image"].annotations.openWorldHint is True
                for name in ("list_styles", "search_reference_images"):
                    assert tools[name].annotations.readOnlyHint is True
                schema = tools["generate_image"].inputSchema
                assert set(schema["properties"]) == {"prompt", "reference_image", "aspect_ratio", "style", "quality"}
                assert schema["required"] == ["prompt"]
                styles = await session.call_tool("list_styles", {})
                assert len(json.loads(styles.content[0].text)) == 21
                refs = await session.call_tool("search_reference_images", {"query": "科技海报", "limit": 2})
                assert json.loads(refs.content[0].text)
                result = await session.call_tool("generate_image", {"prompt": "SDK circle", "quality": "low"})
                assert not result.isError
                data = json.loads(result.content[0].text)
                assert Path(data["path"]).is_file()
                assert data["size"] == "24x12"
                print("V5: 3 tools; annotations correct; 21 styles; search=nonempty (original examples); fake generate=OK")
                print(json.dumps({n: t.annotations.model_dump() for n, t in tools.items()}, ensure_ascii=False))
                bad = await session.call_tool("generate_image", {"prompt": "test", "reference_image": "https://127.0.0.1/a.png"})
                assert bad.isError
                assert "test-only-key" not in bad.content[0].text
    asyncio.run(check())
    assert len(calls) == 1
