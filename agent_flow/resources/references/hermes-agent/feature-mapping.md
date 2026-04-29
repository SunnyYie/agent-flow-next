# Hermes 能力与 agent_flow 映射

| Hermes 能力 | agent_flow 对应资产 | 使用方式 |
|---|---|---|
| Skills（程序性记忆） | `resources/wiki/patterns/workflow/*` | 将成熟流程写成可复用 skill |
| Memory（用户与任务历史） | `resources/wiki/concepts/*` | 记忆关键决策与偏好，跨会话续写 |
| Session Search | 历史需求/实现记录 | 新任务前先检索相似历史 |
| Tools/Toolsets | `resources/wiki/tools/*` | 把 Jira/Lark/CLI 链路封装成工具执行规范 |
| Gateway | 异步任务执行需求 | 远程触发固定流程并回传结果 |
| Cron | 周期性研发任务 | 定时跑日报、巡检、回归检查 |
