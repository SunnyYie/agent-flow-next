# Hooks Templates

本目录按通用程度拆分 Hook 模版，且每个 Hook 只允许存在于一个目录下。

## 目录
- `global/`：通用、低耦合、可跨团队复用
- `team/`：团队统一规范与流程约束
- `project/`：项目/平台耦合能力，依赖项目上下文

## 约束
- Hook 以文件名作为唯一标识（例如 `context-guard.py`）。
- 同名 Hook 不允许出现在多个目录。
- 新增 Hook 时必须先判断归属场景，再放入唯一目录。
