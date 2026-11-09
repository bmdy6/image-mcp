# image-mcp

开发者通过 AI agent 和 OpenAI 兼容接口生成、修改本地图片。

[English](README.en.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/hero-dark.zh-CN.png">
  <img src="docs/readme/hero-light.zh-CN.png" alt="提示词生成蓝色茶壶，参考图改成橙色，结果保存为本地 PNG" width="780">
</picture>

第一轮真实结果：提示词生成蓝壶，再参考它改成橙壶；均为 `low`。[原图、命令与复现说明](docs/readme/demo.md)。

## 快速开始

先列出 21 种风格，不需要 key：

```sh
uvx --from git+https://github.com/bmdy6/image-mcp image-mcp styles
```

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Python ≥3.10；首次运行会安装依赖。列风格不需要 key。

```sh
export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
uvx --from git+https://github.com/bmdy6/image-mcp image-mcp generate "A blue ceramic teapot" --quality low
```

生成需要可用的 key、网络和 Images 接口权限，结果默认保存在当前目录的 `image-mcp-output/`。

## MCP 配置

先确认客户端能在 PATH 找到 `uvx`，替换 key 占位符，再重启客户端或重新连接 MCP。三段均从 GitHub 的 `main` 启动同一个 stdio 服务。

### Claude Code

写入项目根目录的 `.mcp.json`；按客户端提示批准项目 MCP。

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

写入 `~/.codex/config.toml`。

```toml
[mcp_servers.image-mcp]
command = "uvx"
args = ["--from", "git+https://github.com/bmdy6/image-mcp", "image-mcp", "mcp"]

[mcp_servers.image-mcp.env]
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
```

### Cursor

写入项目的 `.cursor/mcp.json`。

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

然后让 agent：「先调用 `list_styles`，再用 `product` 风格生成一张蓝色茶壶图片，画质 `low`。」生成会付费；只调用 `list_styles` 或 `search_reference_images` 不请求生图接口。

配置格式参考：[Claude Code](https://code.claude.com/docs/en/mcp)、[Codex](https://developers.openai.com/codex/mcp)、[Cursor](https://cursor.com/docs/mcp)。

## 你会得到什么

- 提示词或参考图都能生成本地 PNG，并返回绝对路径、实际尺寸、风格与最终提示词。
- 21 种中文风格模板可直接列出并用于生成。
- 离线检索原创参考案例，获得标题、风格、标签和示例提示词。

## 工作流程

1. 调用 `list_styles()` 选模板，或用 `search_reference_images(query, limit)` 查示例。
2. 调用 `generate_image(prompt, reference_image?, aspect_ratio?, style?, quality?)`。
3. 从返回的 `path` 打开本地 PNG；CLI 输出同样的 JSON 字段。

## 命令与选项

| 命令或参数 | 用途 |
|---|---|
| `generate "prompt"` | 生成；`--ref` 接受本地图片或公网 HTTPS 链接。 |
| `--style` | 模板 id，默认 `default`。 |
| `--ratio` / `--quality` | 默认 `1:1` / `low`；完整取值见下方限制。 |
| `styles` / `search "海报" --limit 3` | 离线列模板、查案例。 |
| `mcp` | 启动 stdio 服务。 |

## 21 种风格

| id | 中文名 | 一句话 |
|---|---|---|
| `default` | 默认 | 补充未说明的视觉细节，保留明确要求。 |
| `real` | 真实摄影 | 采用摄影光线、质感与构图。 |
| `product` | 商业产品 | 组织干净的商业产品画面。 |
| `tech_poster` | 科技海报 | 组织科技主题海报与信息层级。 |
| `travel` | 旅行杂志 | 营造旅行杂志的构图与氛围。 |
| `travel_guide` | 旅行手账 | 组织旅行手账或插画攻略。 |
| `interior` | 室内空间 | 表现连贯的室内空间与材质。 |
| `live_stream` | 直播界面 | 组织清晰的直播界面。 |
| `silhouette` | 叙事剪影 | 通过剪影与明暗讲述场景。 |
| `silk_road` | 丝路绘画 | 采用丝路绘画的元素与色彩。 |
| `vintage_5s` | 复古胶片 | 营造怀旧胶片质感。 |
| `ccd_snap` | 日常抓拍 | 采用日常数码相机抓拍风格。 |
| `relation_map` | 关系图谱 | 整理实体及其关系。 |
| `encyclopedia` | 百科图鉴 | 以百科图鉴形式呈现主题。 |
| `restore_old` | 旧照修复 | 引导修复老照片。 |
| `ui_upgrade` | 界面重绘 | 引导界面视觉重绘。 |
| `knowledge_card` | 知识卡片 | 将信息组织为知识卡片。 |
| `product_detail` | 商品详情 | 组织商品详情页面。 |
| `app_ui_design` | 应用界面 | 绘制应用界面。 |
| `campaign_poster` | 活动海报 | 组织活动宣传海报。 |
| `virtual_tryon` | 虚拟试衣 | 引导服装虚拟试穿。 |

## 环境变量

| 变量 | 默认值与用途 |
|---|---|
| `OPENAI_API_KEY` | 生成时必填，使用你自己的 key。 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1`，可设为 OpenAI 兼容 Images 接口。 |
| `IMAGE_MODEL` | `gpt-image-2`；接口必须支持该模型。 |
| `IMAGE_MCP_OUTPUT_DIR` | `./image-mcp-output`，相对服务进程的工作目录。 |
| `IMAGE_MCP_ALLOW_FAKE_IP` | 默认关闭；仅确认代理 fake-ip 后设 `1`，额外放行 `198.18.0.0/15`，其他内网仍拦截。 |

## 常见问题与限制

### 如何计费？

每次生成都按你的 key 计费，`low` 最便宜；也支持 `medium`、`high`、`auto`。具体金额取决于接口、模型和尺寸，失败请求如何计费以服务商为准。

### 参考图安全吗？

链接只读公网 HTTPS，每次重定向都会检查并拦截内网、回环及链路本地地址。本地文件与下载图片均需为静态 PNG、JPEG、WebP 或 GIF，最多 20 MB、4000 万像素、单边 8192；参考图单边超过 2048 会等比缩小。参考图会发送给你配置的接口。

### 画幅和结果有什么限制？

`1:1` 请求 1024×1024；`9:16`、`2:3`、`3:4` 均请求 1024×1536；`16:9`、`3:2`、`4:3` 均请求 1536×1024。返回尺寸以实际图片为准，比例不会逐一精确匹配。

每次只保存一张 PNG，不返回云端 URL。

### 模板和检索能保证效果吗？

模板只是追加提示词，不是专用修复或试衣算法；结果由模型决定。检索仅覆盖 21 条本地原创文字示例，不联网搜图，也没有预览图。

服务仅提供本地 CLI / stdio MCP，不含托管网页、用户系统或云存储；接口请求不读取系统代理环境变量。

## 参与贡献

请在 [Issues](https://github.com/bmdy6/image-mcp/issues) 描述复现步骤，并使用假后端运行测试，避免提交 key 或私有图片。

```sh
uv run --extra test python -m pytest -q
```

## 许可证

[MIT](LICENSE).
