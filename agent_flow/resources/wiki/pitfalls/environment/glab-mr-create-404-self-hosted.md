---
name: glab-mr-create-404-self-hosted
type: pitfall
module: environment
status: verified
confidence: 0.9
created: 2026-04-30
last_validated: 2026-04-30
tags: [environment, gitlab, glab, MR, merge-request, 404, self-hosted, code.taou.com]
---

# glab mr create 在自建 GitLab 上返回 404

## 现象

- `glab mr create --target-branch master` 报 `404 Not Found`
- `glab auth status` 正常，`glab api projects/<path>` 也能正常返回
- 加 `--repo <namespace>/<project>` 显式指定仓库仍 404

## 根因

`glab mr create` 子命令内部的项目路径解析逻辑与 `glab api` 不同。在自建 GitLab（如 code.taou.com）上，`mr create` 的 GraphQL/REST 路径构造可能因版本差异或配置差异导致 404，而直接 API 调用正常。

## 解决方案

**绕过 `glab mr create`，用 `glab api` 直接调 REST API**：

```bash
# 1. 先确认 project ID
glab api projects/<url-encoded-path> | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"

# 2. 用 project ID + form-encoded 参数创建 MR
glab api projects/<ID>/merge_requests \
  --method POST \
  -f source_branch="feat/xxx" \
  -f target_branch=master \
  -f title="feat: xxx" \
  -f description="## Summary\n\n..." \
  -f remove_source_branch=true
```

**注意**：不要用 `--input -` + JSON body，自建 GitLab 会返回 415 Content-Type 不支持。改用 `-f key=value` form-encoded 方式。

## 预防

- 自建 GitLab 上优先用 `glab api` + project ID，不依赖 `glab mr create` 子命令
- 传参用 `-f key=value`，不用 `--input` JSON

## 相关条目

- [[lark-cli-login-shell-path-mismatch|lark-cli 路径不匹配]]
