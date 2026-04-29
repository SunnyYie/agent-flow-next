---
name: cdn-batch-upload
type: tool
module: cdn
status: verified
confidence: 0.99
created: 2026-04-29
last_validated: 2026-04-29
tags: [cdn, upload, images, batch, assets, tool]
---

# CDN 批量上传图片记录

## 目标

将本地目录中的图片批量上传到 CDN，并返回每个文件名对应的 CDN 链接。

## 本次执行

- 执行时间：2026-04-29
- 输入目录：`/Users/sunyi/Downloads/交付物/assets`
- 质量参数：`0.92`
- 执行命令：`python3 -m agent_flow.tools.cdn_upload '/Users/sunyi/Downloads/交付物/assets' --quality 0.92`

## 上传结果

```json
{
  "path": "/Users/sunyi/Downloads/交付物/assets",
  "quality": 0.92,
  "results": {
    "action_comment@3x.png": "https://i9.taou.com/maimai/p/38970/4978_6_41yOli1A3QpXah3i",
    "action_like@3x.png": "https://i9.taou.com/maimai/p/38970/4979_6_52ut15Nn2kg3zNhy",
    "action_share@3x.png": "https://i9.taou.com/maimai/p/38970/4981_6_7Fldp2kaZ6Zan8",
    "arrow_down@3x.png": "https://i9.taou.com/maimai/p/38970/4982_6_81hk6a6CYCQAMVXK",
    "arrow_up@3x.png": "https://i9.taou.com/maimai/p/38970/4983_6_91cYMXSpX5IHcsb0",
    "banner_header@3x.png": "https://i9.taou.com/maimai/p/38970/4984_6_V2lkBA7zQDtItX",
    "chart_bar_left@3x.png": "https://i9.taou.com/maimai/p/38970/4987_6_31IdppVS4QqaHy9U",
    "chart_bar_right@3x.png": "https://i9.taou.com/maimai/p/38970/4988_6_41EQ6sHB3pim6BnC",
    "chart_ring_bg@3x.png": "https://i9.taou.com/maimai/p/38970/4989_6_52zvNqtb2R9RvnBe",
    "chart_ring_icon@3x.png": "https://i9.taou.com/maimai/p/38970/4990_6_64vvu8f81H0HU6P",
    "legend_author@3x.png": "https://i9.taou.com/maimai/p/38970/4993_6_9QinyAytXKBT8W",
    "legend_complaint@3x.png": "https://i9.taou.com/maimai/p/38970/4995_6_V1YQWNux9uxSpV",
    "legend_violation@3x.png": "https://i9.taou.com/maimai/p/38970/4997_6_24NQm4uereS0lQ",
    "legend_vote@3x.png": "https://i9.taou.com/maimai/p/38970/4998_6_3JJC3QgHqkJxL6",
    "post_thumbnail@3x.jpg": "https://i9.taou.com/maimai/p/38970/4999_6_41EmKQ2npfBUaPja",
    "section_analysis@3x.png": "https://i9.taou.com/maimai/p/38970/5000_6_51AKqdOIopsfzex4",
    "section_hot_post@3x.png": "https://i9.taou.com/maimai/p/38970/5001_6_62wp70AunSjlYKLk",
    "section_vitality@3x.png": "https://i9.taou.com/maimai/p/38970/5003_6_8BnivX8HlM2mNg"
  }
}
```

## 使用约束

- 仅允许图片类型：`.png` `.jpg` `.jpeg` `.gif` `.webp` `.svg` `.bmp` `.ico`
- 单文件大小不能超过 `1MB`
- `quality` 只能在 `0.8` 到 `1.0` 之间
- 单个文件失败不能中断整批上传

## 常见问题

1. 报错 `nodename nor servname provided, or not known`

   说明当前执行环境无法访问外网或 DNS 被沙箱限制，需要提权后重试上传命令。

2. 返回结果里没有 `cdn_url`

   需要检查上传接口返回体结构是否变化，并更新 `agent_flow.tools.cdn_upload` 中的 URL 提取逻辑。
