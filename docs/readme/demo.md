# Teapot image example / 茶壶改图示例

These are real results from the first round, reused without new API requests. / 两张图来自第一轮真实生成，本轮未重新请求接口。

[Blue input / 蓝色参考图](smoke-text.png) → [Orange result / 橙色结果](smoke-edit.png)

The original 1024×1024 images are resized to 640×640, with no cropping or retouching. PNG chunks are limited to IHDR, IDAT and IEND: no text, EXIF or other ancillary metadata. / 原图仅等比缩放、移除元数据，没有裁切或修饰。

The commands shown in the hero use the exact recorded prompts and options. Only the local reference path is shortened to `smoke-text.png`. After installing image-mcp, run from a folder containing that file with your API key configured. These commands create **new paid images**, whose results can differ. / 首图使用实际提示词和参数，仅把本地参考路径写为同名文件；重跑会产生新的付费生成，结果可能不同。

```sh
image-mcp generate 'A small blue ceramic teapot on a plain cream background, soft natural light, no text.' --quality low
image-mcp generate 'Keep the same teapot and composition, change the teapot color from blue to warm orange, no text.' --quality low --ref smoke-text.png
```

The first command saves an automatically named PNG; the historical blue result was renamed `smoke-text.png` before the edit. Output sizes were both 1024×1024, style `default`. / 第一次结果文件名由程序生成，当时先重命名为 `smoke-text.png` 再用于第二次改图；实际尺寸均为 1024×1024，风格为 `default`。
