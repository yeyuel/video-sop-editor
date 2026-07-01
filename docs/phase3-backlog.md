# 三期 Backlog

> 二期（Sprint 1～10）已关闭；**三期（Sprint 11～18）已于 2026-06-21 验收关闭**。  
> **总控与执行清单：** [`phase3-master.md`](phase3-master.md) · [`phase3-checklist.md`](phase3-checklist.md)

## 0. 已锁定决策（2026-06-26）

| # | 项 | 结论 | 三期状态 |
|---|-----|------|---------|
| 1 | 剪辑侧 | **开放**（Sprint 12） | ✅ 已交付 |
| 2 | 视频分析 | **LLM Vision**（Sprint 14） | ✅ 已交付 |
| 3 | 镜头复用 | **`allowAssetReuse`，默认关**（Sprint 15） | ✅ 已交付 |
| 4 | OAuth Provider | **OpenAI + Google**（Sprint 16） | ✅ 已交付（Google 订阅 UI 隐藏） |
| 5 | 部署存储 | **单机 SQLite 继续** | ✅ 已交付 |

## 1. 产品边界（四期仍不做）

- 自动粗剪产出**完整成片**（结构导出已在 Sprint 17 交付，不渲染成片）
- 重型素材管理平台（版本、审片、协同批注）
- 网页 Cookie 抓取式 LLM 登录

## 2. 四期 Backlog — 鉴权与 LLM

| 项 | 三期结论 | 四期方向 |
|----|---------|---------|
| 项目级 RBAC / 成员表 | MVP 全项目可见 | 项目成员绑定、配额分角色 |
| Session 外置 | SQLite Session | Redis / 多实例（决策 5 延期） |
| Google Gemini 订阅登录 | UI 隐藏、无配额 | 配额恢复后再开放 |

## 3. 四期 Backlog — 媒体与 AI

| 项 | 三期结论 | 四期方向 |
|----|---------|---------|
| BGM 音频 hash 缓存 | 每次上传全量分析 | 增量重分析、结果版本化 |
| BGM 平台元数据 API | 仅 LLM 推荐 + 本地上传 | 预览 / 版权元数据 API |
| Vision 成本限流 | Mock + 单 Provider 配置 | 配额、队列、批量任务 |

## 4. 四期 Backlog — 协作与导出

| 项 | 三期结论 | 四期方向 |
|----|---------|---------|
| Markdown 反向导入 | 未做 | 非结构化文案解析写回 |
| 标签 / function 全量写回 | 仅 subtitle P0 | export JSON 多字段 apply |
| 分享链接 / 只读预览 | 未做 | 协作增强 |
| 剪映 6+ 加密草稿 | 5.9 明文 JSON | 解密 / 官方 API 调研 |

## 5. 三期已交付摘要（归档）

| 能力 | Sprint |
|------|--------|
| Playwright E2E、lifespan、节拍网格 | 11 |
| 剪辑 RBAC、LLM 审计 | 12 |
| JSON / CSV 导出 round-trip | 13 |
| LLM Vision 预填 | 14 |
| 镜头复用开关 + 全局编排 | 15 |
| OpenAI / Google OAuth + Codex / Gemini 订阅实验 | 16 |
| 剪映草稿导出 + 一键落地 | 17 |
| 验收冻结 `regression-sprint18.md` | 18 |

## 6. 技术债（四期可选）

- 前端 `httpx` → `httpx2`（Starlette 弃用警告）
- Sprint 14 Vision E2E 真实 API smoke（CI 仍用 Mock）
- `draft_meta_info.json` 与 `draft_content.json` 结构分化（剪映 6+）

## 7. 关联文档

- 三期总控：`phase3-master.md`（**已关闭**）
- 三期清单：`phase3-checklist.md`
- 三期回归：`regression-sprint18.md`
- 二期总控：`phase2-master.md`（状态：已关闭）
- Sprint 10 回归：`regression-sprint10.md`
