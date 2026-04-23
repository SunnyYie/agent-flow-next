# Hooks Usage

本场景下的 Hook 按类型拆分。

## 目录
- `runtime/`：运行时行为 Hook
- `governance/`：治理策略 Hook

## 约束
- 每个 Hook 只能在一个场景、一个类型目录中出现。
- 治理类规则放 `governance/`，其余执行类 Hook 放 `runtime/`。
- 文件名使用 kebab-case，并以 `.py` 结尾。
