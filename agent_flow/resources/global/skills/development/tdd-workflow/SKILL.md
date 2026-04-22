# Skill: TDD Workflow

## Trigger
When implementing a new feature or fixing a bug.

## Required Reading
- `.dev-workflow/Agent.md` — 铁律
- `documents/实施计划.md` — 当前任务的完成标志和测试方法
- `.dev-workflow/executor/skills/code_standards.md` — 代码规范

## Procedure

### RED Phase
1. Read the task specification from `documents/实施计划.md`
2. Identify what needs to be tested from "测试方法" section
3. Write failing test(s) that express the expected behavior
4. Confirm tests fail (RED)

### GREEN Phase
5. Write minimum code to make tests pass
6. Run tests to confirm they pass (GREEN)
7. If tests don't pass, iterate on implementation

### IMPROVE Phase
8. Refactor code for clarity and efficiency
9. Re-run tests to confirm still passing
10. Run `ruff check aw/` to check lint

## Commands
```bash
# ⚠️ .venv 在项目根目录，不在 agent-workflow/ 下
/Users/sunyi/ai/sunyi-llm/.venv/bin/pytest agent-workflow/tests/ -v
/Users/sunyi/ai/sunyi-llm/.venv/bin/ruff check agent-workflow/aw/
```

## Rules
- Never write implementation before test (unless task doesn't need tests)
- Each test should verify one behavior
- Use descriptive test names: test_{what}_{condition}_{expected}
- Aim for 80%+ coverage
- Mock external dependencies (LLM calls, subprocess, file I/O)
