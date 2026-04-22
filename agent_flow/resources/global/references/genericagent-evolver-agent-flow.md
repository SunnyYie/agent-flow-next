# GenericAgent / evolver / agent-flow 对比参考

> 参考来源：
> - https://github.com/lsdefine/GenericAgent
> - https://github.com/EvoMap/evolver
> - 当前仓库 `/Users/sunyi/ai/agent-flow`

## 一句话结论

- `GenericAgent` 强在“陌生任务先靠原子工具跑通，再把成功路径结晶成技能树”。
- `evolver` 强在“从日志信号中生成可审计、强约束的演化提示词，并靠停滞检测降低无效修复循环”。
- `agent-flow` 原本强在“项目级开发流程、分层记忆、阶段门控、多 Agent 编排”；本次补强后，新增了一层贴近这两个项目优势的轻量演化闭环。

## 三者关注点

| 项目 | 第一关注点 | 代表资产 |
|------|------------|----------|
| GenericAgent | 任务执行成功率与技能树生长 | 原子工具、执行路径、技能树 |
| evolver | 演化治理与审计 | Genes、Capsules、Events、GEP Prompt |
| agent-flow | 项目开发工作流和长期知识组织 | Memory、Soul、Wiki、Recall、Pipeline |

## 当前 agent-flow 补强后的映射关系

### 1. 技能结晶机制

借鉴 `GenericAgent`：

- 陌生任务第一次允许走探索链路
- 从 `Memory.md` 提取成功路径中的 `[EXECUTE] / [VERIFY] / [SUCCESS]`
- 自动过滤 `[ERROR] / [FAIL]` 与重复步骤
- 将稳定路径固化为 `.dev-workflow/skills/` 中的技能
- 同步更新 `.agent-flow/state/skill-tree.json`
- 结晶技能内置治理信息：`Validation Command`、`Validation Checks`、`Invalidation Conditions`

### 2. 分层记忆

当前 `agent-flow` 的分层已比较完整：

- 短期会话记忆：`.agent-flow/memory/*/Memory.md`
- 长期经验记忆：`.agent-flow/memory/*/Soul.md`
- 长期语义记忆：`.dev-workflow/wiki/`、`.agent-flow/wiki/recall/`、全局 `~/.agent-flow/wiki/`
- 技能树记忆：`.dev-workflow/skills/` + `.agent-flow/state/skill-tree.json`

这比 `GenericAgent` 更偏“项目知识库 + 程序性技能并存”，而不是只押注技能树。

### 3. 状态感知与防死循环

借鉴 `evolver` 的 Signal De-duplication：

- 抽取 `Memory.md` 中的 `[ERROR] / [FAIL] / [FAILED]`
- 对失败签名计数
- 连续 3 次及以上相同失败视为停滞模式
- 在 session-end 生成的 reflection / recall 中记录该结论

当前仍是“检测与复盘优先”，尚未做成执行期硬熔断。

### 4. 严格约束的演化提示词

借鉴 `evolver` 的 GEP Protocol：

- 新增 `EvolutionEngine.build_gep_prompt()`
- 支持 `balanced / innovate / harden / repair-only`
- 输出固定要求：`MutationIntent / Evidence / PlannedChanges / Validation / Rollback`
- 要求先依据日志、技能、记忆、停滞信号做判断，禁止自由发散

### 5. skill-tree 接入运行时上下文

- runtime context 新增 `skill_tree_hits`
- 启动上下文在 THINK 阶段会读取 `.agent-flow/state/skill-tree.json`
- 命中 skill-tree 的技能在推荐排序中会被加权提升，减少“明明已结晶却没被优先调用”的情况

## 这次补强后，agent-flow 仍然没有照搬的点

- 没有复制 `GenericAgent` 的系统级真实设备控制中心化运行时
- 没有复制 `evolver` 的 Gene / Capsule / Event 资产体系和 Hub 网络
- 没有把演化层做成独立产品，而是把它嵌回现有开发工作流

## 适合继续演进的方向

1. 在执行期加入真正的停滞熔断守卫，而不只是 session-end 检测。
2. 给结晶技能增加验证命令和失效条件，接近 `evolver` 的可审计资产。
3. 将 skill-tree 索引纳入 runtime context，使相似任务命中更稳定。
4. 增加“技能复写/退役”机制，避免旧路径长期污染。
