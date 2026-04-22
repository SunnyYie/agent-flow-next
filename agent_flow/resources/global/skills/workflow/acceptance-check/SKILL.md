---
name: acceptance-check
version: 2.0.0
trigger: sub-task complete, 验收, 质量检查, review, 评审, 审查, 验证, 验收标准, 质量审查, acceptance
confidence: 0.90
abstraction: universal
created: 2026-04-13
merged_from: [acceptance-check, quality-review, common-verification-pitfalls]
---

# Skill: Acceptance Criteria Verification

## Trigger

When a sub-task claims to be complete, or when quality review / acceptance is needed for any deliverable.

## Required Reading

- `.dev-workflow/Agent.md` — 铁律（特别是铁律1：双验收、非PASS即FAIL）
- `documents/实施计划.md` — 当前任务的"完成标志"和"测试方法"
- `documents/设计.md` — 设计规格（用于交叉验证一致性）

## Procedure

### Step 1: Find Acceptance Standards (Mandatory First Step)

Before defining any acceptance criteria, find professional standards:

1. Search Skill/Wiki for existing acceptance standards for this deliverable type
2. WebSearch "{交付物类型}验收标准" or "{deliverable type} acceptance checklist"
3. If found → use professional standards as the baseline
4. If not found → draft acceptance criteria and request user confirmation

### Step 2: Determine Acceptance Level

| Level | When to Use | Verification Method |
|-------|-------------|---------------------|
| Lightweight | Non-critical deliverables | Self-review + user confirmation |
| Standard | General deliverables | Verifier Agent + Main Agent dual verification |
| Strict | Security / core modules | Multi-Agent cross-verification |

### Step 3: Read Completion Criteria

1. Read "完成标志" and "测试方法" from `documents/实施计划.md`
2. For each acceptance criterion:
   - Verify it is actually met (not just claimed)
   - Test the specific behavior described
   - Check edge cases not explicitly listed
3. Cross-reference with `documents/设计.md` for consistency

### Step 4: Quality Dimension Check

Check each deliverable against these dimensions:

| Dimension | What to Check | Pass Condition |
|-----------|---------------|----------------|
| Completeness | All requirements covered | No missing requirement points |
| Accuracy | Data/numbers/templates match source | 100% consistent with original |
| Consistency | No contradictions between sections | No conflicting descriptions |
| Compliance | Meets target format/specification | Conforms to applicable standards |
| Security | No sensitive information exposed | No tokens, keys, or internal links |

### Step 5: Pitfall Checklist

Every verification must explicitly check these categories, even if they seem obvious:

#### Category 1: File Existence & Integrity

| Check | Description | Example Pitfall |
|-------|-------------|-----------------|
| File actually exists? | Cannot rely on Executor's claim alone | S1.5 .gitignore missing but report says created |
| File content non-empty? | Empty file != valid file | Empty `__init__.py` is OK; empty `state.py` is not |
| File in correct location? | Path matches implementation plan | Should be `aw/core/` not `aw/` |

#### Category 2: Configuration Completeness

| Check | Description | Example Pitfall |
|-------|-------------|-----------------|
| .gitignore complete? | All ignore patterns listed | S1.5 missed `.ruff_cache/` |
| pyproject.toml consistent? | Dependency versions, entry points match code | CLI entry `aw = "aw.cli.main:cli"` must verify |
| Tool config effective? | `target-version`, `line-length` correct | Should be `py310`, `120` |

#### Category 3: Code-Design Alignment

| Check | Description |
|-------|-------------|
| Field names match design docs? | TypedDict field names must have no deviation |
| Enum values match design docs? | `Phase.PRD = "prd"` not `"PRD"` |
| Function signatures match plan? | Parameter types, return types |
| No scope creep? | No extra features, comments, or type annotations |

#### Category 4: Import & Dependency Chain

| Check | Description |
|-------|-------------|
| New module importable? | `python -c "from aw.core.state import ..."` |
| `__init__.py` exports? | Package `__init__.py` exposes public API |
| Circular dependencies? | Mutual imports cause ImportError |

#### Category 5: Test Quality

| Check | Description |
|-------|-------------|
| Tests actually verify behavior? | Not just "no exception thrown" |
| Boundary conditions covered? | Empty input, max values, None |
| Mocks reasonable? | Mock behavior matches real behavior |
| Tests independent? | No implicit dependencies between tests |

### Step 6: Select Verification Depth

Choose depth based on task complexity:

| Depth | For Tasks | Check Scope |
|-------|-----------|-------------|
| L1 Basic | Simple file creation | File exists + content non-empty + lint |
| L2 Standard | Feature implementation | L1 + code-design alignment + tests pass + import verification |
| L3 Deep | Core modules (state/executor/plugin) | L2 + boundary conditions + security check + dependency chain integrity |
| L4 Strict | Security layer / workflow engine | L3 + adversarial testing + concurrency safety + integrity proof |

### Step 7: Reality Check Protocol

Default stance: NEEDS WORK. Only upgrade to PASS when every criterion has concrete evidence.

```
For each acceptance criterion:
  1. Is it claimed to be met?     → No claim = FAIL
  2. Is there concrete evidence?  → No evidence = FAIL
  3. Is the evidence credible?    → "tests pass" needs pytest output as proof
  4. Are there omissions?         → Check against Pitfall Checklist item by item
  5. Conclusion: PASS or FAIL     → No "partial pass"
```

### Step 8: Generate Verification Report

```
[VERIFY-REPORT] S{x.y}: {task_title}
- Acceptance Level: {Lightweight/Standard/Strict}
- Verification Depth: {L1/L2/L3/L4}
- Acceptance Criteria:
  ✅ {criterion 1}: PASSED - {evidence}
  ❌ {criterion 2}: FAILED - {reason}
    → Fix suggestion: {repair advice}
- Quality Dimensions:
  ✅ Completeness: {evidence}
  ✅ Accuracy: {evidence}
  ❌ Consistency: {issue description}
  ✅ Compliance: {evidence}
  ✅ Security: {evidence}
- Pitfall Checklist:
  ✅ File existence & integrity: checked
  ✅ Configuration completeness: checked
  ❌ Code-design alignment: {specific issue}
  ✅ Import & dependency chain: checked
  ✅ Test quality: checked
- Issues Found: {count}
- Overall: PASS / FAIL
```

## Common Acceptance Standards Reference

### Requirements Specification

| Check Item | Method | Pass Condition |
|------------|--------|----------------|
| Completeness | Check against original doc item by item | All business requirements covered |
| Accuracy | Spot-check numbers, templates, constraints | 100% consistent with original |
| No redundancy | Check for intros/background/placeholders | No redundant meta-information |
| No sensitive data | Search for tokens/keys/internal links | No internal technical identifiers |
| Format compliance | Check against standard template | Conforms to specification format |

### Code Delivery

| Check Item | Method | Pass Condition |
|------------|--------|----------------|
| Functional correctness | Run tests | All tests pass |
| Code standards | Lint check | No standards violations |
| Security | Security scan | No security vulnerabilities |
| No redundancy | Code review | No unused code |

## Rules

- Never mark PASS based on claim alone — must have concrete evidence
- File existence must be verified with a command, not just by reading a report
- Each acceptance criterion must have independent concrete evidence
- Security issues always FAIL regardless of other criteria
- If ambiguous, flag and ask — don't assume
- Non-PASS = FAIL, no "partial pass"
- FAIL must include specific problem and fix suggestion
- Must search for professional acceptance standards before defining criteria — never fabricate standards
- Discover issues should be recorded in SOUL.md dynamic section
