---
name: batch-upload-images-to-cdn
version: 1.0.0
trigger: 上传图片到cdn, 批量上传图片到cdn, 上传 assets/icons 图片到cdn, upload images to cdn, upload icon images
confidence: 0.95
abstraction: universal
created: 2026-04-29
updated: 2026-04-29
---

# Skill: batch-upload-images-to-cdn

## Trigger
当用户要求把某个图片目录或单个图片文件批量上传到 CDN，并返回每个图片对应链接时触发。

## Procedure
1. 提取用户输入里的本地路径，例如 `上传/Users/sunyi/xxxx/assets/icons图片到cdn上`。
2. 使用 `python3 -m agent_flow.tools.cdn_upload "<path>" --quality 0.9` 执行批量上传。
3. 上传前必须校验：
   - 仅允许图片类型：`.png` `.jpg` `.jpeg` `.gif` `.webp` `.svg` `.bmp` `.ico`
   - 单文件大小不能超过 `1MB`
4. 读取脚本输出的 JSON：
   - 成功项包含 `name`、`status=uploaded`、`cdn_url`
   - 失败项包含 `name`、`status`、`reason`
5. 直接把 JSON 返回给用户，不要改写成自然语言列表，除非用户明确要求解释。

## Rules
- 未拿到明确本地路径时，不要猜测路径。
- `quality` 只能在 `0.8` 到 `1.0` 之间，默认使用 `0.9`。
- 对目录执行时按批量处理；对单文件执行时也复用同一 JSON 输出结构。
- 单个文件失败不能中断整批上传，必须保留其他文件结果。
- 如果路径不存在、没有可上传图片、或接口未返回 CDN 链接，要把错误写入 JSON 结果。
