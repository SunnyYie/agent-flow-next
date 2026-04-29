# Skill: Security Verification Checks

## Trigger

When verifying any sub-task that involves: user input handling, file I/O, subprocess execution, API endpoints, or authentication. Inspired by Security Engineer pattern — assume hostile inputs.

## Required Reading

- `.agent-flow/Agent.md` — 铁律（安全最高优先级）
- `documents/设计.md` — 第3节安全设计

## Security Verification Checklist

### S1: Input Validation

| 检查项 | 方法 | 预期 |
|--------|------|------|
| 外部输入是否经过校验？ | 审查代码中的 Pydantic 验证 | 所有外部入口有验证 |
| 路径输入是否防遍历？ | 检查 `../` 处理 | 拒绝 `../` 路径 |
| 字符串输入是否防注入？ | 检查 SQL/命令拼接 | 使用参数化查询 |

### S2: Command Execution Safety

| 检查项 | 方法 | 预期 |
|--------|------|------|
| 子进程命令是否经过白名单？ | 检查 `allowedTools` 配置 | 非白名单工具不可用 |
| 是否有命令黑名单拦截？ | 审查 `SecurityMiddleware` | `rm -rf`、`DROP TABLE` 等被拦截 |
| 环境变量是否安全传递？ | 检查敏感信息泄露 | 无密钥在命令行参数中 |

### S3: File Access Control

| 检查项 | 方法 | 预期 |
|--------|------|------|
| Agent 是否在 Worktree 内操作？ | 检查工作目录限制 | 不超出 Worktree 边界 |
| 受保护文件是否不可访问？ | 验证 `.env`、`*.key` 等 | 读/写均被拦截 |
| 日志是否追加模式？ | 检查文件打开模式 | `"a"` 模式，无删除/修改方法 |

### S4: Data Exfiltration Prevention

| 检查项 | 方法 | 预期 |
|--------|------|------|
| URL 输出是否被过滤？ | 检查 pastebin/gist 等目标 | 数据外泄 URL 被阻止 |
| 网络请求是否受限？ | 审查 `allowedTools` | 无未授权的外部请求 |

### S5: Permission Model

| 检查项 | 方法 | 预期 |
|--------|------|------|
| Frontend/Backend Agent 不能 push main/develop | 检查 Git 权限规则 | 仅 Reviewer Agent 可合并 |
| Reviewer Agent 独占 push 权限 | 检查 `allowedTools` | 只有 Reviewer 有 merge 权限 |
| 审计日志不可篡改 | 检查 `AuditLogger` API | 无 update/delete 方法 |

## Security Test Patterns

### Pattern 1: Blacklist Command Injection

```python
def test_blacklist_command_intercepted():
    middleware = SecurityMiddleware()
    is_safe, reason = middleware.validate_command("rm -rf /")
    assert is_safe is False
    assert "denied" in reason.lower()
```

### Pattern 2: Protected File Access

```python
def test_protected_file_blocked():
    middleware = SecurityMiddleware()
    is_allowed, reason = middleware.validate_file_access(".env", "read")
    assert is_allowed is False
```

### Pattern 3: URL Exfiltration Prevention

```python
def test_data_exfiltration_url_blocked():
    middleware = SecurityMiddleware()
    is_allowed, reason = middleware.validate_url("https://pastebin.com/api/post")
    assert is_allowed is False
```

### Pattern 4: Audit Log Immutability

```python
def test_audit_log_append_only():
    logger = AuditLogger(log_dir)
    # 验证没有 update/delete 方法
    assert not hasattr(logger, "update_action")
    assert not hasattr(logger, "delete_action")
```

## Severity Classification

| 级别 | 定义 | 验收影响 |
|------|------|----------|
| CRITICAL | 可导致数据泄露、系统破坏 | 一票 FAIL |
| HIGH | 可导致未授权访问 | 一票 FAIL |
| MEDIUM | 违反安全最佳实践 | 需修复但不阻塞 |
| LOW | 安全增强建议 | 记录，不阻塞 |

## Rules

- 安全问题没有"部分通过"——CRITICAL 和 HIGH 一律 FAIL
- 验证时假设所有外部输入都是恶意的
- 安全检查结果记录到 SOUL.md
- 新发现的安全模式补充到本 Skill
