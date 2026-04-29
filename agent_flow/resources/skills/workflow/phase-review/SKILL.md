# Skill: Phase Review and Summary

## Trigger
When all sub-tasks in a phase are completed and dual-verified.

## Required Reading
- `.agent-flow/Agent.md` — 铁律和流程
- `documents/实施计划.md` — 各任务的完成标志和测试方法
- `.agent-flow/state/completed_tasks.md` — 已完成任务记录

## Procedure

1. Review all completed sub-tasks in the phase
2. For each sub-task, confirm:
   - Implementation matches design doc specification (`documents/设计.md`)
   - All acceptance criteria met (对照实施计划"完成标志")
   - Tests passing
   - No security issues
3. Generate phase summary
4. Execute [PHASE-CLEANUP] — 检查并关闭所有残留子Agent
5. Update `.agent-flow/state/current_phase.md` and `.agent-flow/state/completed_tasks.md`
6. Update `.agent-flow/logs/dev_log.md`
7. Present summary to user
8. **停止，等待用户确认**
9. **用户验收确认（v3.0 新增）**

### Step 9: 用户验收确认

当用户确认阶段产出后，创建/追加用户验收标记：

写入 `.agent-flow/state/.user-acceptance-done`：
```
phase={phase_name}
status=accepted
timestamp={ISO8601}
task={当前任务描述}
confirmed_by=user
summary={用户确认摘要}
```

多个阶段使用空行分隔多条记录。

**按复杂度的验收要求**：
- **Simple**: 只需在 Implement 阶段完成后创建一次（`implement=accepted`）
- **Medium**: Plan + Implement 各创建一次（`plan=accepted` + `implement=accepted`）
- **Complex**: Research + Plan + Implement 各创建一次（`research=accepted` + `plan=accepted` + `implement=accepted`）

**此标记至关重要**：`user-acceptance-guard.py` hook 会在 `git push` 和 MR 创建时检查此标记。无标记 = 推送被阻断。

**绝对禁止**：不经用户确认就自行创建此标记。必须在用户明确说"可以"/"验收通过"/"继续"等肯定话语后才创建。

## Output Format

```
[PHASE-SUMMARY] Phase {n}: {name}
- Completed: {task list with PASS status}
- Issues: {resolved issues}
- Deviations: {any changes from plan}
- Next: {preview of next phase}
- Status: AWAITING USER APPROVAL
```

## Phase Cleanup Checklist

```
[PHASE-CLEANUP] Phase {n}
- Executor Agent: CLOSED / STILL RUNNING
- Verifier Agent: CLOSED / STILL RUNNING
- All sub-agents cleaned: YES / NO
- User acceptance marker: CREATED / NOT YET (waiting for user)
```
