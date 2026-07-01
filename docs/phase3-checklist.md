# 三期执行清单

## 1. 文档目的

本文档用于把三期工作拆成可跟踪事项。优先级分为 `P0 / P1 / P2`，Sprint 11～18 按迭代推进；勾选状态请在开发过程中持续维护。

**已锁定决策**见 `phase3-master.md` §4：

1. 剪辑侧开放  
2. LLM Vision 视频分析  
3. 镜头复用 + 项目开关（默认关）  
4. OAuth 目标：OpenAI + Google  
5. 部署：**单机 SQLite 继续**（不引入 Redis）

## 2. 当前状态概览

| 阶段 | 状态 | 说明 |
|------|------|------|
| 二期 | ✅ 已关闭 | Sprint 1～10 |
| Sprint 11（工程基线） | ✅ 已完成 | E2E、lifespan、节拍网格对齐 |
| Sprint 12（剪辑 + RBAC） | ✅ 已完成 | **决策 1** |
| Sprint 13（导出反向导入） | ✅ 已完成 | JSON / CSV round-trip |
| Sprint 14（LLM Vision） | ✅ 已完成 | **决策 2**；2026-06-21 关闭 |
| Sprint 15（全局分镜 + 复用） | ✅ 已完成 | **决策 3** |
| Sprint 16（OAuth + Provider 合并） | ✅ 已完成 | **决策 4** |
| Sprint 17（粗剪结构） | ✅ 已完成 | EDL 导出 + 剪映/FCPXML 调研 |
| Sprint 18（验收冻结） | ✅ 已完成 | 三期关闭（2026-06-21） |
| **三期** | ✅ **已关闭** | 立项 2026-06-26；关闭 2026-06-21 |

## 3. Sprint 迭代计划

### Sprint 11 — 工程基线 + 三期立项

- [x] 新增 `phase3-master.md` / 本清单 / 更新 `docs/README.md`
- [x] Playwright E2E：导演主流程 smoke（登录 → 主题 → BGM → 分镜 → 导出）
- [x] FastAPI `lifespan` 替换 `@app.on_event("startup")`
- [x] 前端节拍吸附网格与后端 `resolve_validation_beat_points` 对齐
- [x] `phase2-checklist.md` §10.1「过时勾选同步」补 ✅
- [x] 新增 `regression-sprint11.md`

**验收：** pytest 全绿 + E2E 1 条通过 + verify-workflow 7 checks。

---

### Sprint 12 — 剪辑侧开放 + RBAC MVP（决策 1）

**登录与门禁**

- [x] 登录页：支持已启用用户列表 / 用户名密码（非仅硬编码 director）
- [x] `uiEnabled=false` 账号拒绝登录并提示联系导演
- [x] 剪辑角色隐藏：LLM 设置、用户管理、系统级 Provider 路由
- [x] Topbar / 导航按角色显示能力说明

**权限模型**

- [x] 定义 `require_director_user` / `require_project_editor` 依赖
- [x] 剪辑：项目内 assets / themes / rhythm / storyboard / export 读写
- [x] 导演：保留全部能力 + 用户 CRUD
- [x] migration 015（如需要）：项目成员表或 role 扩展 — **MVP 跳过，全项目可见**
- [x] **决策 5**：Session / OAuth token / 审计日志均 SQLite，不引入 Redis

**审计（P1）**

- [x] LLM 调用日志：userId、endpoint、token 估算、status
- [x] 导演可查看最近 N 条（简单列表即可）

**回归**

- [x] E2E：剪辑账号走通全流程且无法进入 `/settings/llm`
- [x] `test_regression_sprint12.py`（角色门禁）

**验收：** 导演创建剪辑用户 → 剪辑登录完成一个项目导出。

---

### Sprint 13 — 导出 ↔ 分镜反向导入

**JSON 导入（P0）**

- [x] 定义 export JSON schema version 字段
- [x] `POST /projects/{id}/import/export-json` dry-run + apply
- [x] 冲突策略 UI：覆盖 subtitle / 跳过 / 预览 diff
- [x] 写回范围：subtitle（P0）；function / tags（P1）

**CSV 导入（P1）**

- [x] 列映射向导（segmentId / start / end / subtitle / assetId）
- [x] 导入前 validation 预览

**测试**

- [x] 导出 JSON → 修改 → 导入 → 分镜字段一致
- [x] `test_regression_sprint13.py`

**验收：** round-trip 无数据丢失；dry-run 不修改 DB。

---

### Sprint 14 — LLM Vision 素材预填（决策 2）

**PRD 与设计**

- [x] 编写 `docs/prd-video-analysis.md`（帧数、成本、字段、失败策略）
- [x] migration 013：`vision_analysis_json`、`vision_analysis_status`

**后端**

- [x] ffmpeg 抽帧服务（可配置 interval / max_frames）
- [x] Vision 分析 service：结构化 JSON 输出
- [x] 支持 Provider：**Google Gemini Vision** + **OpenAI GPT-4o 类** + **Kimi k2.5/k2.6**（配置切换）
- [x] 实时模型能力检测（`GET /models` + 启发式 + 缓存）
- [x] 异步任务 + SSE 进度（复用现有 LLM 流式模式）
- [x] 视频文件 hash 缓存（同文件不重分析，按 fingerprint 复用 Vision 结果）

**前端**

- [x] 素材表单：「AI 分析」按钮 + 进度 + 预填高亮
- [x] Vision 分析 `LlmProgressOverlay` 阶段进度（与主题/分镜/节奏等 LLM 页一致）
- [x] 预填字段待确认态；保存后写入正式 tags
- [x] 分析失败 InlineErrorBanner + 手工录入不受影响
- [x] LLM 设置：非 Vision 模型自动提示
- [x] 录入页连续录入：目录扫描 session 持久化、保存后跳下一条未录入文件
- [x] 录入/素材 workflow UI 对齐设计 token（`ProjectPageLayout`、深绿 + 紫 AI）

**前端 UI：** ✅ 已完成（2026-06-21）

**测试**

- [x] fixture / mock Vision 响应（CI 不调真实 API）
- [x] `test_regression_sprint14.py`

**验收：** 上传样例视频 → 分析 → ≥3 字段预填 → 人工改后保存。

**Sprint 14：** ✅ 已完成（2026-06-21）

---

### Sprint 15 — 全局分镜编排 + 镜头复用（决策 3）

**项目开关**

- [x] migration 014：`allow_asset_reuse` default false
- [x] 新建 / 项目设置 UI 开关 + 说明文案
- [x] API / schema / `api.md` 同步

**生成逻辑**

- [x] `allowAssetReuse=false`：保持现有一素材一次约束
- [x] `allowAssetReuse=true`：LLM / 规则生成允许多段同一 assetId
- [x] 全局编排 prompt：主题 + 全素材摘要 + 节拍 + 目标时长
- [x] validation：复用段数 / 同一素材总时长占比 warning（issues 非 hard fail）

**前端**

- [x] 分镜列表复用镜头 badge
- [x] 生成前读取开关；LLM meta 说明是否启用复用

**文档**

- [x] 更新 `prd.md` §4 / §5.3 镜头复用口径

**测试**

- [x] 开关 off/on 各一套生成结果
- [x] `test_regression_sprint15.py`

**验收：** 开关关行为与二期一致；开关开可生成同一素材 2+ 分镜且 validation 有提示。

**Sprint 15：** ✅ 已完成（2026-06-21）

---

### Sprint 16 — OpenAI + Google OAuth（决策 4）

**Registry / 合并**

- [x] `openai-compatible` 并入 `openai`（别名兼容 + migration 015 数据迁移）
- [x] Google Provider 增加 `oauth` authType
- [x] OpenAI OAuth 配置项：client_id、redirect_uri、scopes（环境变量）

**后端 OAuth 流**

- [x] migration 015：oauth token + pending state 表
- [x] Authorization Code + PKCE：start / callback / refresh / revoke
- [x] Google OAuth 2.0 与 OpenAI OAuth 各一套 adapter
- [x] Gateway 按 auth_type 注入 Bearer（api_key | oauth）

**前端**

- [x] LLM 设置页：API Key | OAuth 连接
- [x] OAuth 跳转 + callback 结果 toast
- [x] 授权失效重新连接引导

**部署**

- [x] README：OAuth callback URL、Google Cloud Console / OpenAI App 配置说明

**测试**

- [x] OAuth state/PKCE 单元测试
- [x] stub callback 集成测试（`LLM_OAUTH_MOCK`）
- [x] 手工：OpenAI 授权 1 次（Codex 订阅登录已走通）；Google 无配额且 UI 已隐藏，不再作为 Sprint 16 验收项

**验收：** OAuth 连接后可跑连通性测试 + 主题 LLM 建议。

**Sprint 16：** ✅ 已完成（2026-06-21）

**Sprint 16b — ChatGPT (Codex) + Gemini 订阅登录（实验性）**

- [x] 新增 auth 类型：`codex_oauth`（OpenAI）、`gemini_subscription`（Google）
- [x] Codex：CLI 同源 OAuth（`localhost:1455` loopback）+ Codex Responses Gateway
- [x] Gemini：Gemini CLI 同源 OAuth + Code Assist / GenAI Gateway
- [x] LLM 设置页：API Key | Platform OAuth | ChatGPT 登录 | Google 订阅登录
- [x] Mock 模式（`LLM_OAUTH_MOCK=true`）可本地回归
- [x] 迁移 016：`oauth_mode` / `account_id` / `project_id` 字段

**验收：** Mock 下 Codex/Gemini 订阅登录 + 连通性测试通过；真实环境需 ChatGPT Plus / Google AI 订阅。

**Sprint 16b：** ✅ 已完成（2026-06-21）

---

### Sprint 17 — 粗剪结构输出（P1）

- [x] 剪映草稿 JSON 导出（`capcut` 格式，优先于 EDL）
- [x] 剪映草稿根目录配置（`jianyingDraftRoot`，默认 `%LOCALAPPDATA%` 路径）
- [x] 一键写入剪映草稿目录（`draft_content.json` + `draft_meta_info.json`）
- [x] BGM 上传时自动导出 audio 轨（无 BGM 不阻断）
- [x] 导出页 **写入剪映草稿目录** 主按钮 + JSON 下载 + EDL
- [x] `test_export_capcut.py` + `test_regression_sprint17_export.py`

**验收：** 导出页一键写入后，剪映草稿列表可直接打开粗剪时间线（不渲染）。

**Sprint 17：** ✅ 已完成（2026-06-21，含剪映自动落地）

---

### Sprint 18 — 验收冻结 + 三期关闭

- [x] `regression-sprint18.md`：pytest + E2E + 四决策验收表
- [x] E2E：导演 + 剪辑双角色 smoke
- [x] `phase3-master.md` 状态 → 三期已关闭
- [x] `phase3-backlog.md` 未做项标四期
- [x] README 部署清单（OAuth、Vision、角色）
- [x] §2 本清单全部 P0 Sprint 勾选

**验收：** 满足 `phase3-master.md` §10 关闭标准。

**Sprint 18：** ✅ 已完成（2026-06-21）

## 4. P0 必做项汇总

| 领域 | 关键交付 | Sprint |
|------|---------|--------|
| 协作 | 剪辑登录 + 分权 | 12 |
| 导入 | JSON 导出 round-trip | 13 |
| AI 输入 | LLM Vision 预填 | 14 |
| 编排 | 镜头复用开关 + 全局 LLM | 15 |
| 接入 | OpenAI + Google OAuth | 16 |
| 质量 | E2E + 全量 pytest | 11、18 |

## 5. P1 / P2（三期可选）

| 项 | Sprint | 说明 |
|----|--------|------|
| CSV 反向导入 | 13 | P1 |
| 音频文件 hash 缓存（BGM 节拍识别） | — | P1，移出 Sprint 14 |
| 粗剪结构导出 | 17 | P1 |
| LLM 调用审计 UI 增强 | 12 | P1 |
| Markdown 反向导入 | 四期 | 非 P0 |
| Redis Session / 多实例 | — | **四期** | 决策 5：三期单机 SQLite |
| BGM 平台元数据 API | 四期 | 调研项 |
| 分享链接 / 只读预览 | 四期 | 协作增强 |

## 6. 关键路径回归命令

```powershell
cd backend
python -m pytest tests/ -q

cd ..
node scripts/verify-workflow.mjs
npx playwright test   # Sprint 11 起
```

## 7. 关联文档

- 总控：`phase3-master.md`
- 需求池：`phase3-backlog.md`
- LLM 规范：`phase2-llm-integration-standard.md`
- Migration：`schema-migration.md`
- 二期归档：`phase2-checklist.md`
