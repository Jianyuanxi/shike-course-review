# PowerContext 的记忆模型

PowerContext 用 Scope 隔离不同项目或用户的上下文。每个 Scope 包含 Source journal、Memory、Review Inbox、Handoff history 和 Topic Memory。Scope ID 是数据分区标识，不等同于用户身份认证。

Source 用来保存证据，例如一次查询、一份文档或一个任务结果。Atomic Memory 用来保存可复用的事实、偏好、约束和决策。显式写入 Atomic Memory 不需要生成模型，因此应用可以用确定性规则记录学习状态。

# Artifact 与 Revision

Artifact 是具有稳定身份的记忆对象，Revision 是不可变内容版本。更新记忆时先读取当前内容和 ETag，再通过 If-Match 提交完整内容，可以避免并发写入互相覆盖。历史 Revision 仍然可读，适合审计学习记录如何形成。

遗忘不等于物理删除。处于 forgotten 状态的内容不再参与普通召回，但历史仍然保留并可以恢复。active 状态的记忆才参与普通搜索和上下文召回。

# Basic memory 与 Full memory

Basic memory 支持显式保存和读取，不要求额外的模型 API。Full memory 可以从 Source 自动提取记忆并支持语义召回，但需要配置生成模型与 embedding 服务。课程复习助手把文档语义检索交给 seekdb，把学习行为和薄弱点交给 PowerContext，因此使用 Basic memory 即可。

来源：OceanBase PowerContext 官方 README 与 Atomic Memory 文档。本文为依据公开文档整理的原创课程笔记，并非官方文档原文。
