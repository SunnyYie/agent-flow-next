# Skill: Implementation Patterns

## Trigger

When implementing features — especially extending existing modules or creating new ones.

## Required Reading

- `.dev-workflow/Agent.md` — 铁律（文档驱动、不做超范围实现）
- `documents/设计.md` — 设计规格
- `.dev-workflow/executor/skills/code_standards.md` — 代码规范

## Pattern 1: Extend, Don't Overwrite

**场景**：在已有文件中追加新功能（如 S2.2 在 state.py 中追加序列化函数）

**流程**：

1. 先用 Read 工具读取当前文件完整内容
2. 确认已有代码的位置和结构
3. 用 Edit 工具在合适位置插入新代码
4. 绝不使用 Write 工具覆盖已有文件（除非是全新文件）

**反模式**：用 Write 工具重写整个文件，丢失已有实现

## Pattern 2: Pydantic Model + TypedDict Dual Definition

**场景**：需要同时有运行时类型提示和校验能力（如 WorkflowState + WorkflowStateModel）

> 详细模式说明和代码示例见 [[pydantic-patterns|skills/python/pydantic-patterns/handler]] Pattern 1。

**原则**：

- TypedDict 用于日常状态传递（零开销）
- Pydantic Model 仅用于边界校验（磁盘读取、API 输入）
- 两者字段定义必须保持同步

## Pattern 3: Enum with String Value

**场景**：需要枚举值同时是字符串（用于 JSON 序列化、LangGraph 状态比较）

**模式**：

```python
class Phase(str, Enum):
    PRD = "prd"
    PLAN = "plan"
```

**好处**：`Phase.PRD == "prd"` 为 True，可直接用于 JSON 和状态比较

## Pattern 4: Factory Function with Sensible Defaults

**场景**：创建复杂状态对象的默认实例（如 `default_workflow_state()`）

**模式**：

```python
def default_workflow_state() -> WorkflowState:
    return WorkflowState(
        phase=Phase.PRD.value,       # 从枚举取值
        api_changed=False,            # 布尔默认 False
        rejection_count=0,            # 计数器默认 0
        file_map=[],                  # 列表默认空
        code_paths={},                # 字典默认空
        # 其余字符串默认 ""
    )
```

## Pattern 5: YAML → Pydantic Validation Pipeline

> 详细模式说明和代码示例见 [[pydantic-patterns|skills/python/pydantic-patterns/handler]] Pattern 5 和 Pattern 6。

## Pattern 6: Graceful Serialization with Type Conversion

**场景**：序列化可能包含非 JSON 原生类型（datetime 等）的字典

**模式**：

```python
def _convert_datetime(obj):
    """递归转换 datetime 为 ISO 字符串"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _convert_datetime(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_datetime(item) for item in obj]
    return obj
```

**原则**：序列化前做递归类型转换，反序列化后无需还原（保持字符串形式即可）

## Pattern 6: Import Inside Function for Circular Avoidance

**场景**：两个模块互相引用（如 state.py 引用 state_schema.py）

**模式**：

```python
def validate_state(state_dict):
    from aw.core.state_schema import WorkflowStateModel  # 延迟导入
    model = WorkflowStateModel.model_validate(state_dict)
    return model.model_dump()
```

## Rules

- 扩展已有文件时永远先 Read 再 Edit，绝不用 Write 覆盖
- 新建文件才使用 Write 工具
- 保持 TypedDict 和 Pydantic Model 的字段同步
- 枚举类继承 `(str, Enum)` 以支持 JSON 序列化
