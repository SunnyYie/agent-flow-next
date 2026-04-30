在真实项目（示例：`/Users/sunyi/web/maimai_react_native/rn`）中执行 Agent-flow 全流程，覆盖需求分析、任务拆解、开发实现、测试验收与交付闭环。

## 阶段复盘（前两阶段核心问题）

1. 初始化后缺少“插件/Hook 就绪提示与校验”，导致执行过程无法保证严格遵循规范。
2. 项目级 `CLAUDE.md`、`AGENTS.md` 缺少统一模板，输出格式和约束不一致。
3. 遇到飞书需求链接时，Agent 未严格执行“先查本地 wiki/skill 再外网”的检索顺序。
4. 前端需求提取缺少统一结构（UI vs 功能），任务拆解格式不稳定。
5. `wiki/project-structure.md` 的生成时机不稳定，未固定在“初步需求列表之后”。
6. 需求澄清提问后缺少“是否已足够开工”的复判机制，容易过度追问或带着不确定开发。
7. SubAgent 执行分支/Jira 流程时缺少硬约束，可能跳过既有 wiki/skill 或随意填字段。
8. 流程目前偏人工分步推进，自动化执行与门控不清晰。

## 优化目标

让 Claude Code 在项目中默认按标准流程自动推进，并在关键风险点触发门控确认；所有步骤可追溯、可复核、可复用。

## 执行模式

1. 默认模式：自动化连续执行（阶段内自动推进）
2. 门控模式：仅在“阶段门控点”暂停等待用户确认
3. 强制规则：未满足前置条件时禁止进入下一阶段

---

## 1. 初始化与环境就绪（自动）

### 1.1 初始化检查

- 检查项目根目录是否存在 `/.agent-flow`
- 不存在则使用 `agent-flow-team` 初始化

### 1.2 项目协议文件模板检查

- 检查项目根目录是否存在 `CLAUDE.md`、`AGENTS.md`
- 不存在则按统一模板生成（见模板文档）

### 1.3 Hook/插件就绪检查（新增强制）

- 检查 `.claude/settings*.json` 是否已注册 Agent-flow 关键 Hook
- 检查当前任务依赖的插件/skills 是否可用
- 缺失时必须先补齐；`hook-readiness-guard` 会硬阻断实现与变更命令

### 1.4 协议关联

- 将 `.agent-flow` 使用规则、优先级与入口文档关联到 `CLAUDE.md`/`AGENTS.md`

### 1.5 2026-04-30 新增更新（必须执行）

- 老项目初始化后，额外执行一次升级同步：

```bash
agent-flow plugin update --scope project --all --only-outdated
agent-flow plugin verify
agent-flow doctor --json
```

- 验证 skills 运行时注册：

```bash
ls -la .claude/skills .agents/skills
```

- 必须存在：
  - `.claude/skills/agent-flow-project`
  - `.agents/skills/agent-flow-project`
  - `.agent-flow/state/skill-registrations.json`

**阶段门控点 G1（可选停）**
- 条件：初始化、模板、Hook、插件、skills 注册全部就绪

---

## 2. 需求分析与任务拆解（自动 + 门控）

需求文档示例：`https://maimai.feishu.cn/wiki/OQeiwoJZ6iSyj7kT9HUcKN6An9b`

### 2.1 需求来源识别与检索顺序（新增强约束）

当输入包含飞书链接或疑似需求文档时，必须按顺序执行：

1. 查项目内 `.agent-flow/wiki`、`.agent-flow/skills` 的相关记录
2. 查 `agent-flow-team` 全局 wiki/skills
3. 仍无结论再使用 web search
4. 若本地 + web 都无法解决，才向用户汇报阻塞并给出候选方案

禁止跳过 1/2 直接 WebSearch。

### 2.2 文档读取与前端需求提取

- 使用 `lark-cli` 或可用飞书能力读取文档
- 提取“前端相关需求点”，并强制区分：
  - UI需求（视觉、布局、样式、交互反馈）
  - 功能需求（业务逻辑、状态流转、接口/埋点、权限等）
- 产出统一格式“初步需求列表”（使用模板）

### 2.3 结合后端技术文档与需求文档生成需求列表和任务（按条件执行）

- 在完成前端初步需求提取后，按条件进入：
  - 若用户提供后端技术文档：读取并对齐（接口文档、数据模型、鉴权规则、错误码规范、性能约束等）
  - 若用户未提供后端技术文档：必须向用户确认关键数据格式与接口约束后再继续
- 将“需求文档的业务目标”与“后端技术约束/能力边界（文档或用户确认）”做逐项对齐，补齐以下信息：
  - 接口依赖与调用时序
  - 字段映射与数据兼容要求
  - 鉴权、状态流转与异常分支
  - 埋点、日志与验收口径
- 输出“可执行需求列表（前后端对齐版）”，每条需求必须包含：
  - 需求描述（业务目标 + 技术约束）
  - 类型（UI/功能/联调）
  - 优先级与前置依赖
  - 依据来源（后端文档链接或用户确认记录）
- 基于该列表生成任务清单，至少包含：
  - 前端实现任务
  - 联调与验证任务
  - 异常与回归测试任务

### 2.4 生成 `project-structure.md`（时机修正）

- 在“初步需求列表”完成后再生成/更新 `.agent-flow/wiki/project-structure.md`
- 内容必须为“关键词/Tag → 代码目录与关键实现点映射”，不写操作流程

### 2.5 任务拆解与代码关联

- 按需求列表拆解任务，映射到具体代码文件/模块
- 输出任务清单 + 代码关联证据给主Agent审核

### 2.6 不确定项提问与复判机制（新增）

每轮提问后必须复判：

1. 是否已满足开发前置条件（边界、异常、兼容、回滚）
2. 是否仍有必须由用户决策的关键项
3. 若已可开工，禁止继续追问，进入计划与执行

硬约束：
- 每次 `AskUserQuestion` 后必须完成 `.clarification-recheck-done`，否则 `clarification-guard` 阻断实现
- 禁止“问一步停一步”；`clarification-guard` 会在无进展时阻断连续提问

### 2.7 Jira/分支监督（新增强约束）

监督 SubAgent 必须：

1. 先读分支与 Jira 对应 wiki/skill
2. 按标准流程创建/复用 Jira 与子任务并流转状态
3. 对“需业务决策字段”必须请求用户确认，禁止填随意值
4. 可用默认值仅限明确约定项：
   - 开发预估工期=8
   - 端=RN
   - 需求目标=OKR相关
   - 需求描述默认不填写
   - 相关角色默认=sunyi

硬约束：
- Jira 变更命令前必须有 `.jira-context-ready`
- 使用非默认字段必须有 `.jira-field-decision-confirmed`
- 命令中出现占位值（如 `xxx/todo/tmp/随便`）会被 `jira-workflow-guard` 阻断

**阶段门控点 G2（建议停）**
- 条件：需求拆解、代码映射、不确定项复判通过、Jira/分支就绪

---

## 3. 代码实现与测试验证（自动）

### 3.1 开发前检查

- 监督 Agent 判断分支是否符合规范（命中主干分支禁止直接开发）
- Jira 状态应为“开发中”

### 3.2 串并行策略

- 根据任务依赖图自动判断串行/并行
- 并行任务必须独立记录变更与测试证据

### 3.3 实现执行

- Coder SubAgent 按确认计划开发
- 遇到不明确需求：先内部检索/思考，再升级主Agent；仍无法解决再询问用户

### 3.4 测试与证据

- 单测/集成/手工验证按任务适配
- 必须记录命令输出、日志、截图或可复现证据

### 3.5 Jira 同步

- 监督 SubAgent更新 Jira 进度与备注，保持可追溯

### 3.6 2026-04-30 新增更新（Hook 阻断排障）

若出现：

- `PreToolUse ... preflight-enforce.py`
- 或 `No stderr output`（历史问题）

处理顺序：

1. 不要重复执行同一 Edit/Write/Bash
2. 先完成 pre-flight 缺失项（`current_phase.md` / `.complexity-level`）
3. 再继续代码修改

推荐先执行只读检索：

```bash
Read .agent-flow/skills/Index.md
Read .agent-flow/wiki/INDEX.md
```

**阶段门控点 G3（可选停）**
- 条件：代码实现完成，测试证据齐全，风险已登记

---

## 4. 交付验收与总结反馈（自动 + 门控）

### 4.1 首轮验收

- Coder 提交交付包
- 主Agent派发验收 SubAgent进行独立验收（PASS/FAIL）

### 4.2 二轮验收

- 修复后进行二次验收，直到通过

### 4.3 用户确认

- 主Agent汇总结果并请求用户确认
- 未通过则回到修复闭环

### 4.4 发布闭环

- 监督 SubAgent 更新 Jira 为已完成
- 推送分支并创建 PR

### 4.5 经验沉淀

- 主Agent收集各 SubAgent 复盘
- 按“触发频率 + 通用性”决定沉淀到项目级或 team 级 wiki/skills

### 4.6 2026-04-30 新增更新（交付前最小校验）

交付前固定执行：

```bash
agent-flow plugin verify
agent-flow doctor --json
```

要求：

- `plugin hooks verified: OK`
- `doctor` 返回 `"ok": true`

**阶段门控点 G4（建议停）**
- 条件：用户确认通过，Jira/PR闭环完成，总结已沉淀

---

## 自动化可实现性判断

可以实现“自动执行 + 门控确认”的混合流程：

1. 可自动化：初始化检查、模板生成、检索顺序、需求拆解模板化、project-structure 生成、Jira标准流转、测试证据收集、交付清单。
2. 必须人工门控：业务歧义决策、关键设计取舍、非默认 Jira 字段、最终验收确认。
3. 推荐策略：默认自动推进，仅在 G2/G4 强制停顿；G1/G3 作为可配置停顿点。

