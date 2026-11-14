> [!IMPORTANT]
> This project has been merged into [Visionary](https://github.com/bmdy6/visionary) (web app + AI assistant + MCP with shared credits). This repository is archived and no longer maintained.

# image-mcp

Generate and edit local images from your AI agent, or [change the pose or outfit of the same character](#change-a-characters-pose-or-outfit).

[简体中文](README.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/hero-dark.png">
  <img src="docs/readme/hero-light.png" alt="A prompt creates a blue teapot; reference editing turns it orange, saved as a local PNG" width="780">
</picture>

Recorded results: prompt → blue teapot; reference → orange teapot, both at `low`. [Images, commands and reproduction](docs/readme/demo.md).

## Quick start

```sh
uvx --from git+https://github.com/bmdy6/image-mcp image-mcp styles
```

The command lists 21 styles without an API key.

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python ≥3.10; dependencies install on first use. Listing styles needs no key.

```sh
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
uvx --from git+https://github.com/bmdy6/image-mcp image-mcp generate "A blue ceramic teapot" --quality low
```

The API generation command above needs a valid key, a network connection, and Images API access. Results default to `image-mcp-output/` in the current directory.

## MCP configuration

Ensure the client can find `uvx` on PATH. All three configurations launch the same stdio server from GitHub `main`. To update an existing installation, run the command below and reconnect MCP or restart the client.

```sh
uvx --refresh --from git+https://github.com/bmdy6/image-mcp image-mcp styles
```

### Claude Code

Use `.mcp.json` in the project root and approve the project MCP when prompted.

```json
{
  "mcpServers": {
    "image-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bmdy6/image-mcp",
        "image-mcp",
        "mcp"
      ],
      "env": {
        "OPENAI_API_KEY": "YOUR_OPENAI_API_KEY"
      }
    }
  }
}
```

### Codex

Add this to `~/.codex/config.toml` to prepare references and use Codex's built-in image generation.

```toml
[mcp_servers.image-mcp]
command = "uvx"
args = ["--from", "git+https://github.com/bmdy6/image-mcp", "image-mcp", "mcp"]
```

To also call `generate_image` through the API, add the block below to the same file and replace the placeholder.

```toml
[mcp_servers.image-mcp.env]
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
```

### Cursor

Use `.cursor/mcp.json` in the project.

```json
{
  "mcpServers": {
    "image-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/bmdy6/image-mcp",
        "image-mcp",
        "mcp"
      ],
      "env": {
        "OPENAI_API_KEY": "YOUR_OPENAI_API_KEY"
      }
    }
  }
}
```

To try API generation, ask your agent to use Image MCP's `generate_image` to draw a blue teapot with style `product` and quality `low`. The `list_styles`, `search_reference_images`, and `prepare_pose_image` tools work without a key.

Configuration references: [Claude Code](https://code.claude.com/docs/en/mcp), [Codex](https://developers.openai.com/codex/mcp), [Cursor](https://cursor.com/docs/mcp).

## What you get

- Generate local PNG images from prompts or references, returning absolute paths, actual dimensions, style and final prompt.
- Repose the same character with a pose sketch, optionally using a separate outfit reference.
- List and apply 21 built-in Chinese style templates.
- Search original local examples for titles, styles, tags and sample prompts.

## How it works

1. Choose with `list_styles()` or find examples with `search_reference_images(query, limit)`.
2. Call `generate_image` with `reference_image` for one reference or `reference_images` for up to four ordered references.
3. Open the local PNG at the returned `path`; the CLI returns the same JSON fields.

### Change a character's pose or outfit

| Original character | Waving | Arms extended |
| --- | --- | --- |
| ![Original robot character](docs/readme/pose-character.png) | ![The same robot waving with its right hand](docs/readme/pose-wave.webp) | ![The same robot with both arms extended](docs/readme/pose-arms-wide.webp) |

Both samples came from Codex's built-in image generation, using the same [character image](docs/readme/pose-character.png) with either the [waving sketch](docs/readme/pose-wave-guide.png) or the [arms-extended sketch](docs/readme/pose-arms-wide-guide.png). The samples follow the pose and retain the colors and chest star, with some change in leg proportions.

Save the character image and pose sketch locally and try this prompt in Codex.

> Use Image MCP's `prepare_pose_image` with `pose-character.png` and `pose-wave-guide.png`. Keep the character's face, outfit, and colors, then generate the image with `$imagegen`.

The tool accepts absolute paths to local images and optional `outfit_image` and `extra_prompt` arguments. It returns a `prompt` and ordered `reference_images` for the character, optional outfit, and pose.

Codex sessions with built-in image generation can use both fields directly. Usage follows the Codex sign-in method. To use the Images API, pass both fields to `generate_image`. The provider must support edits with multiple references and bills the configured API key. [Codex image generation](https://learn.chatgpt.com/docs/image-generation)

The reference order was inspired by [Lanpose](https://github.com/wzc520pyfm/gen-ai-pose-image). Use your own references or assets you have permission to use.

## Commands / options

| Command / option | Purpose |
|---|---|
| `generate "prompt"` | Generate. Repeat `--ref` in order for local images or public HTTPS URLs. |
| `--style` | Template id; default `default`. |
| `--ratio` / `--quality` | Default `1:1` / `low`; see limits below. |
| `styles` / `search "海报" --limit 3` | List styles or search local examples offline. |
| `mcp` | Start the stdio server. |

## 21 styles

| id | Chinese name | Description |
|---|---|---|
| `default` | 默认 | Fill unspecified visual details while preserving explicit requirements. |
| `real` | 真实摄影 | Use photographic lighting, texture and composition. |
| `product` | 商业产品 | Create clean commercial product imagery. |
| `tech_poster` | 科技海报 | Arrange a technology poster with clear hierarchy. |
| `travel` | 旅行杂志 | Use travel-magazine composition and atmosphere. |
| `travel_guide` | 旅行手账 | Organize a travel journal or illustrated guide. |
| `interior` | 室内空间 | Show interiors with coherent space and materials. |
| `live_stream` | 直播界面 | Compose a readable live-stream interface. |
| `silhouette` | 叙事剪影 | Tell a scene through silhouettes and contrast. |
| `silk_road` | 丝路绘画 | Use Silk Road painting motifs and colors. |
| `vintage_5s` | 复古胶片 | Emulate nostalgic film texture. |
| `ccd_snap` | 日常抓拍 | Use a casual compact-camera snapshot aesthetic. |
| `relation_map` | 关系图谱 | Lay out entities and their relationships. |
| `encyclopedia` | 百科图鉴 | Present a subject as an illustrated encyclopedia. |
| `restore_old` | 旧照修复 | Guide an old-photo restoration. |
| `ui_upgrade` | 界面重绘 | Guide a visual interface redraw. |
| `knowledge_card` | 知识卡片 | Arrange information as a knowledge card. |
| `product_detail` | 商品详情 | Compose a product-detail page. |
| `app_ui_design` | 应用界面 | Draft an application interface. |
| `campaign_poster` | 活动海报 | Structure a promotional event poster. |
| `virtual_tryon` | 虚拟试衣 | Guide a clothing try-on image. |

## Environment variables

| Variable | Default and purpose |
|---|---|
| `OPENAI_API_KEY` | Required when Image MCP calls the Images API. |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1`; an OpenAI-compatible Images endpoint can be used. |
| `IMAGE_MODEL` | `gpt-image-2`; your endpoint must support the model. |
| `IMAGE_MCP_OUTPUT_DIR` | `./image-mcp-output`, relative to the server process working directory. |
| `IMAGE_MCP_ALLOW_FAKE_IP` | Off by default; set `1` only for a confirmed proxy fake-IP setup. Allows `198.18.0.0/15`; other private addresses remain blocked. |

## FAQ / limitations

### What does it cost?

Image MCP's API calls are billed to the configured key. Pricing depends on the provider, model, size, and quality. Codex's built-in image generation follows the session's sign-in method.

### Which references are accepted?

URL references allow public HTTPS only; every redirect is checked against private, loopback and link-local addresses. Local and downloaded images must be static PNG, JPEG, WebP or GIF, at most 20 MB, 40 million pixels and 8192 pixels per edge. References above 2048 pixels per edge are resized proportionally and sent to your configured API.

### What are the output limits?

`1:1` requests 1024×1024. `9:16`, `2:3` and `3:4` all request 1024×1536; `16:9`, `3:2` and `4:3` request 1536×1024. Returned dimensions reflect the actual image; ratios are approximate.

Each call saves one PNG, with no cloud URL.

### Do presets or search guarantee results?

Presets append prompt hints; restoration and try-on are model instructions rather than dedicated algorithms. Search covers 21 original local text examples, with no web search or preview images.

Only a local CLI and stdio MCP are provided, without a hosted UI, accounts or cloud storage. API requests do not use proxy environment variables.

## Contributing

Describe reproduction steps in [Issues](https://github.com/bmdy6/image-mcp/issues) and test against a fake backend; keep keys and private images out of commits.

```sh
uv run --extra test python -m pytest -q
```

## License

[MIT](LICENSE).
