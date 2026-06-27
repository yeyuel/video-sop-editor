# 三期 Backlog

> 二期（Sprint 1～10）已关闭。本文档汇总**明确移出二期**的能力，供三期规划使用。  
> **总控与执行清单：** [`phase3-master.md`](phase3-master.md) · [`phase3-checklist.md`](phase3-checklist.md)

## 0. 已锁定决策（2026-06-26）

| # | 项 | 结论 |
|---|-----|------|
| 1 | 剪辑侧 | **开放**（Sprint 12） |
| 2 | 视频分析 | **LLM Vision**（Sprint 14；Google Gemini + OpenAI GPT-4o 类） |
| 3 | 镜头复用 | **允许，项目级开关 `allowAssetReuse`，默认关**（Sprint 15） |
| 4 | OAuth Provider | **OpenAI + Google**（Sprint 16） |
| 5 | 部署存储 | **单机 SQLite 继续**（Redis / 多实例 → 四期） |

来源：`phase2-checklist.md` §7、§10.3、§6.4 及 Sprint 10 评估结论。

## 1. 产品边界（三期仍不做）

- 自动粗剪产出**完整成片**（可评估结构准备，但不承诺一键成片）
- 重型素材管理平台（版本、审片、协同批注）
- 网页 Cookie 抓取式 LLM 登录

## 2. P0 候选 — 鉴权与 LLM 接入

| 项 | 现状（二期） | 三期目标 | 备注 |
|----|------------|---------|------|
| OAuth / Device Code | API stub 501 | 实装授权码 / 设备码流程 | **OpenAI + Google**（见 §0）；Sprint 16 |
| 多角色 RBAC | 导演 / 剪辑 + `uiEnabled` 门禁 | 项目级权限、LLM 配额分角色 | **剪辑侧开放**；Sprint 12 |
| Session 持久化 | SQLite `authsessionentity` | 维持 SQLite + 可选 Refresh Token 表 | **决策 5**：不迁 Redis；四期再评估 |

## 3. P1 候选 — 媒体与 AI 深化

| 项 | 现状（二期） | 三期目标 | 备注 |
|----|------------|---------|------|
| 视频内容分析 | 无 | 镜头类型 / 场景 / 情绪自动建议 | **LLM Vision**；Sprint 14 |
| 素材自动标签 | 手工录入 tags | 上传后预填 emotion / visual tags | 与 Vision 合并；Sprint 14 |
| 更强分镜组织 | 规则 + LLM 二层排序 | 大模型全局编排、镜头复用策略 | **复用开关**；Sprint 15 |
| BGM 平台集成 | LLM 推荐歌名 + 用户上传 | 可选预览 / 版权元数据 API | 不做盗版下载链路 |
| 音频分析缓存 | 每次上传全量分析 | 增量重分析、分析结果版本化 | 配合 BGM 工作流 |

## 4. P2 候选 — 协作与导出

| 项 | 二期结论 | 三期方向 |
|----|---------|---------|
| **导出 → 分镜反向导入** | **不做**（见 §5 评估） | Markdown/JSON 解析写回 subtitle、tags、function；需冲突策略 UI |
| 完整脚本写回 | 仅 `segmentCaptions` → subtitle | 标题/标签/封面建议双向同步 |
| 自动粗剪结构 | 仅文档评估 | 输出 EDL / 剪映草稿结构，不渲染成片 |
| 导出协作 | 下载为主 | 分享链接、只读预览、版本对比 |

## 5. 导出写回评估（Sprint 10）

### 5.1 已实现（二期保留）

- LLM 导出建议返回 `segmentCaptions: [{ segmentId, subtitle }]`
- 后端 `apply_export_captions_to_segments` 写回分镜 `subtitle`
- API `meta.storyboardCaptionsUpdated` 告知前端同步条数
- 单元测试：`test_export_generation.py`；集成测试：`test_regression_sprint10.py`

### 5.2 未做（建议三期）

| 能力 | 不做原因 | 三期工作量 |
|------|---------|-----------|
| Markdown 反向导入 | 需解析非结构化文案 + 段落对齐算法 | 中 |
| JSON/YAML 全量导入 | 需 schema 版本、字段冲突与回滚 UI | 中～大 |
| CSV 反向导入 | 列映射与校验复杂，易误操作 | 中 |
| 标签 / function 写回 | 与导出页编辑模型不一致 | 小～中 |

**结论**：二期以「LLM 导出建议 → 字幕写回」为闭环即可；**完整反向导入列入三期「协作编辑」**，不在二期 scope creep。

## 6. 技术债（可选三期初）

- FastAPI `on_event("startup")` → lifespan handlers
- 前端 `httpx` → `httpx2`（Starlette 弃用警告）
- OAuth provider 配置 UI 与后端 stub 对齐
- E2E 浏览器测试（Playwright）覆盖主流程

## 7. 关联文档

- 三期总控：`phase3-master.md`
- 三期清单：`phase3-checklist.md`
- 二期总控：`phase2-master.md`（状态：已关闭）
- 执行清单：`phase2-checklist.md`
- Sprint 10 回归：`regression-sprint10.md`
