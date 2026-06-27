# 三期开发主控文档

## 1. 文档目标

本文档作为三期总控入口，统一说明三期开发的目标、**已锁定决策**、边界、优先级和实施顺序。执行清单见 `phase3-checklist.md`。

## 2. 当前项目所处阶段

截至 **2026-06-26**：

- 一期 / 二期主工作流已完整跑通（Sprint 1～10 已关闭）
- 三期正式立项，Sprint 11 起按本主控推进
- 需求池来源：`phase3-backlog.md`（二期移出项 + Sprint 10 评估结论）

## 3. 三期目标

在三期稳定主流程上，增强四类能力：

1. **协作**：剪辑侧开放，导演 / 剪辑分权
2. **输入**：LLM Vision 视频分析，素材自动预填
3. **编排**：允许镜头复用（项目级开关），全局分镜 LLM 编排
4. **接入**：OpenAI + Google OAuth 实装（保留 API Key 并存）

仍不做：完整成片渲染、重型 DAM、Cookie 抓取登录、盗版 BGM 下载。

## 4. 已锁定关键决策（2026-06-26）

| # | 决策 | 结论 | 影响范围 |
|---|------|------|---------|
| 1 | 剪辑侧是否开放 | **开放** | Sprint 12：登录、路由门禁、用户管理、项目权限 |
| 2 | 视频分析技术路线 | **LLM Vision** | Sprint 14：抽帧 → Vision API；需成本限流与失败兜底 |
| 3 | 镜头复用 | **允许，项目级开关** | Sprint 15：`allowAssetReuse` 默认关；开时 validation 规则扩展 |
| 4 | OAuth 目标 Provider | **OpenAI + Google** | Sprint 16：Authorization Code + PKCE；Google 用于 Gemini Vision / OAuth |
| 5 | 部署与存储 | **单机 SQLite 继续** | 三期不引入 Redis / 多实例；Session、OAuth Token、审计均落 SQLite |

### 4.1 决策 1 — 剪辑侧开放

- 剪辑账号通过 `uiEnabled=true` 登录（migration 008 已有用户表）
- **导演**：项目 CRUD、LLM Provider 配置、用户管理、全流程
- **剪辑**：项目内素材 / 主题 / 节奏 / 分镜 / 导出读写；**不可**改 LLM Provider / 用户管理
- Session 继续 SQLite + Bearer Token（见决策 5）

### 4.2 决策 2 — LLM Vision

- 素材上传或手动触发分析 → ffmpeg 抽关键帧 → Vision 模型输出结构化建议
- 预填字段：`shotType`、`emotionTags`、`visualTags`、`informationDensity`、`scene`（可选）
- 分析结果标 `analysisStatus: pending | ready | failed`；失败不阻塞手工录入
- Provider 优先级：与 OAuth 决策对齐，**Google Gemini Vision + OpenAI GPT-4o 类** 可配置

### 4.3 决策 3 — 镜头复用 + 开关

- 项目字段新增 `allowAssetReuse: boolean`（默认 `false`，与一期口径兼容）
- 关：保持「一素材一分镜」生成约束
- 开：分镜生成允许同一 `assetId` 出现多次；validation 增加「复用段时长 / 总占比」提示（非硬阻断）
- UI：新建 / 项目设置页开关；分镜列表标注复用镜头

### 4.4 决策 4 — OpenAI + Google OAuth

- 实装 stub 替换：`/llm/providers/{id}/oauth/start`、callback、token refresh
- Registry 新增 **Google** Provider（OAuth + API Key；Gemini API base）
- OpenAI：OAuth + 现有 API Key + Device Code（若官方仍支持则一并实装）
- 前端 LLM 设置页：「API Key」与「OAuth 连接」双 Tab；callback URL 写入 README 部署说明

### 4.5 决策 5 — 单机 SQLite 继续

- **三期不引入 Redis、对象存储或多实例 Session**；部署形态与二期一致（单进程 FastAPI + 本地 SQLite 文件）
- 继续沿用：`schemaversionentity` 编号 migration、`authsessionentity`、Fernet 加密 LLM Key
- 三期新增数据（OAuth token、Vision 分析 JSON、LLM 审计）**全部写入 SQLite**
- Refresh Token 若需要，存 SQLite 表即可，不做分布式会话
- **四期再评估**：Redis Session、读写分离、分析任务队列外置（仅当有多实例 / 高并发需求）

## 5. 一期 / 二期基线（不变）

- 工作流：新建 → 录入 → 主题 → 节奏 → 分镜 → 导出
- 分镜生成参考节奏节拍；BGM analyzed 门禁保持
- 目标时长最小 5 秒；规则排序 + LLM 二层排序保留

## 6. Sprint 路线图（11～18）

| Sprint | 主题 | 优先级 | 依赖决策 |
|--------|------|--------|---------|
| **11** | 工程基线 + E2E | P0 | — |
| **12** | 剪辑侧 + RBAC MVP | P0 | 决策 1 |
| **13** | 导出 ↔ 分镜反向导入 | P0 | — |
| **14** | LLM Vision 素材预填 | P0 | 决策 2 |
| **15** | 全局分镜 + 镜头复用开关 | P0 | 决策 3 |
| **16** | OpenAI / Google OAuth | P0 | 决策 4 |
| **17** | 粗剪结构输出（EDL / 剪映 JSON） | P1 | — |
| **18** | 验收冻结 + 三期关闭 | P0 | 全部 |

推荐顺序：**11 → 12 → 13 → 14 → 15 → 16 → 17 → 18**

Sprint 14 可与 13 部分并行（不同模块）；Sprint 16 可在 12 之后尽早启动 OAuth 基础设施，与 14 共用 Google 配置。

## 7. 三期边界

**不做（写入四期 backlog 或永久不做）：**

- 自动粗剪渲染完整成片
- 重型素材管理平台（版本、审片批注）
- 网页 Cookie 抓取式 LLM 登录
- **Redis / 多实例 Session / 外置任务队列**（决策 5：单机 SQLite 继续，四期再评估）
- BGM 平台盗版下载 / 预览 API（可选 P2 调研，非 P0）

## 8. 数据结构与 Migration 预告

| Migration | 内容 | Sprint |
|-----------|------|--------|
| 012 | `allow_asset_reuse` on project | 15 |
| 013 | 素材 `vision_analysis` JSON + status | 14 |
| 014 | OAuth token 表（provider、user、refresh、expires） | 16 |
| 015 | 项目成员 / 角色绑定（若 008 不够用） | 12 |
| 016 | LLM 调用审计日志 | 12 |

每次 migration 同步 `schema-migration.md`、`api.md`。

## 9. 测试与回归策略

- 每个 Sprint 结束：`pytest` 全绿 + `verify-workflow.mjs`
- Sprint 11 起：Playwright E2E 主流程（导演 + 剪辑各 1 条）
- Sprint 13：导出 JSON round-trip 集成测试
- Sprint 14：Vision mock / fixture 测试（避免 CI 调真实 Vision API）
- Sprint 16：OAuth flow 单元测试 + 手工 callback smoke
- Sprint 18：`regression-sprint18.md` 冻结清单

## 10. 三期关闭标准（草案）

1. `phase3-checklist.md` 中 P0 Sprint（11～16、18）全部勾选
2. 剪辑账号可独立完成项目（决策 1）
3. Vision 预填 + 人工确认流可用（决策 2）
4. `allowAssetReuse` 开关与 validation 行为符合 PRD 更新（决策 3）
5. OpenAI + Google OAuth 至少各 1 条手工授权成功（决策 4）
6. 部署仍为单机 SQLite，无 Redis 依赖（决策 5）
7. E2E + pytest 全绿；`phase3-backlog.md` 剩余项标四期

**状态：三期进行中（立项 2026-06-26）**

## 11. 关联文档

- 需求池：`phase3-backlog.md`
- 执行清单：`phase3-checklist.md`
- 二期归档：`phase2-master.md`、`phase2-checklist.md`
- LLM 规范：`phase2-llm-integration-standard.md`
- 产品基线：`prd.md`（Sprint 15 需补镜头复用 §）
- 视频分析 PRD（待写）：`prd-video-analysis.md`（Sprint 14 前）
