# 二期执行清单

## 1. 文档目的

本文档用于把二期工作拆成可跟踪事项。优先级分为 `P0 / P1 / P2`，Sprint 按迭代推进；勾选状态请在开发过程中持续维护。

## 2. 当前状态概览（截至 2026-06-25）

| 阶段 | 状态 | 说明 |
|------|------|------|
| 一期主流程 | ✅ 已可用 | 新建 → 录入 → 主题 → 节奏 → 分镜 → 导出 |
| Sprint 1（P0 工程收口） | ✅ 已完成 | 服务拆分、migration 001、workflow 联动、提示统一 |
| Sprint 2（音频节拍） | ✅ 已完成 | librosa + 能量兜底、剪映踩点语义、rawBeatPoints、migration 002/003 |
| Sprint 3（P0 收尾 + 文档对齐） | ✅ 已完成 | 回归测试、字段变更 SOP、文档同步 |
| Sprint 4（节奏模块深化） | ✅ 已完成 | 暗场能量分析、细/粗踩点、LLM 节奏文案、曲名真实化 |
| Sprint 5（LLM 网关标准化） | ✅ 已完成 | Gateway、Provider 配置页、SSE 进度、Kimi 兼容、stream 回归 |
| Sprint 6（LLM 业务质量） | ✅ 已完成 | 主题证据字段、导出平台化、rawBeat 切镜、LLM 二层排序、字幕写回 |
| Sprint 7（用户与鉴权） | ✅ 已完成 | Session Token、用户 API 预留、LLM Key Fernet 加密 |
| Sprint 8（P2 增强） | ✅ 核心已完成 | 校验四件套、CSV 导出、BGM 推荐工作流 |
| Sprint 9（交互统一） | ✅ 已完成 | TimeSecondsInput、AssetSelector、ConfirmDialog、列表布局统一 |
| **二期收尾** | 🔄 规划中 | Sprint 9～10：交互统一 + 验收冻结（见 §10） |

## 3. Sprint 迭代计划

### Sprint 1 — P0 工程收口 ✅

- [x] 拆分 `repository` 生成型逻辑（`storyboard_generation` / `export_generation` / `serialization`）
- [x] 建立 migration 001（`schemaversionentity` + legacy columns）
- [x] workflow 解锁逻辑修正（节奏 → 分镜）
- [x] 统一 BlockingNotice / ToastNotice 提示口径

### Sprint 2 — 音频节拍识别 ✅

- [x] librosa 主识别 + 能量起音兜底
- [x] 扩展音频格式（ffmpeg 转 WAV）
- [x] `analysisSource` 区分 rule / audio_upload / rule_fallback
- [x] migration 002（`detected_bpm`、`audio_duration_sec`）
- [x] migration 003（`raw_beat_points`）
- [x] 剪映踩点语义对齐（踩节拍1 粗密度 / 踩节拍2 细密度 / 强弱拍）
- [x] 切换 `beatMode` 时基于 raw 节拍重新采点
- [x] 识别失败回退规则生成、删除音频、旧文件清理
- [x] 节奏页展示 BPM / 时长 / 识别说明
- [x] 单元测试（`test_beat_grid.py`、`test_audio_analysis.py`）

### Sprint 3 — P0 收尾 + 文档对齐 ✅

- [x] 更新本清单 Sprint 状态（随迭代维护）
- [x] `docs/schema-migration.md` 补 migration 003
- [x] `docs/prd.md` §8.1 同步节奏字段当前实现
- [x] `docs/phase2-master.md` 同步 Sprint 计划引用
- [x] 新增字段变更 SOP：见 `schema-migration.md` §6 字段变更检查清单
- [x] 关键路径最小回归清单：见 `regression-sprint3.md`（17 pytest + workflow 脚本）
- [x] `.gitignore` 补 `*.tsbuildinfo`
- [x] `docs/api.md` 补 `rawBeatPoints` 字段说明

### Sprint 4 — 节奏模块深化 ✅

- [x] **暗场建议 `darkCutSuggestions`**：能量局部低谷 + 固定比例兜底
- [x] **`selectedTrackName` 真实化**：上传文件名 / 用户填写 / 主题参考曲名
- [x] **剪映点位更接近**：细/粗两档 onset（librosa onset + beat_track / 能量双阈值）
- [x] **`rhythmNotes` / `bgmStyle` LLM 化**：LLM 生成 + 模板兜底（`rhythm_copy.py`）
- [x] **旧节奏计划补 raw**：保存时从 beatPoints 回填 raw/coarse 缓存

### Sprint 5 — LLM 网关标准化 ✅

- [x] Provider Registry（多厂商 base_url / model / timeout）
- [x] 统一 Auth Service（完善 API Key，预留 OAuth / Device Code stub）
- [x] LLM Gateway（超时、重试、JSON 解析失败、空响应兜底）
- [x] 前端区分 LLM 未配置 / 超时 / 解析失败 / 规则兜底
- [x] 配置管理长期方案（环境变量 → DB 配置表 migration 005/006）
- [x] LLM 设置页（保存 / 激活 / 连通性测试）
- [x] 主流程 SSE 流式进度（主题 / 分镜 / 节奏 / 导出）
- [x] 浏览器直连 FastAPI，规避 Next.js 代理超时
- [x] Kimi K2 兼容（temperature=0.6、关闭 thinking、JSON 解析增强）
- [x] 主题 / 分镜 prompt 瘦身与 `max_tokens` 上限
- [x] LLM 流式接口回归：`regression-sprint5.md` + `test_llm_stream.py`
- [ ] OAuth / Device Code 实装 → **移三期**（stub 已留，非二期关闭阻塞项）

### Sprint 6 — LLM 业务质量 ✅

**主题建议**

- [x] 候选间差异度控制（`_enforce_theme_diversity` + prompt 约束）
- [x] 可解释性：标注用了哪些素材 / 地点（`usedAssetIds` / `usedLocations` + migration 007）
- [x] 失败兜底策略文档化（`regression-sprint5.md` §5）+ 前端提示（`describeLlmStatus`）

**分镜建议**

- [x] 结合 `rawBeatPoints` + 踩点模式做 beat 对齐切镜（`resolve_storyboard_beat_points`）
- [x] 地点连续性校验强化（validation 文案 + 前端 toast 联动）
- [x] LLM 排序作为二层来源，保留规则排序兜底（`merge_asset_order`）
- [x] 「适配节拍」开关与 validation 结果联动（生成后校验提示）

**导出建议**

- [x] 按平台差异化标题、标签、文案风格（小红书 / 抖音 guide）
- [x] 导出结果写回时间线字幕（`segmentCaptions` → 分镜 subtitle）

### Sprint 7 — 用户与鉴权 ✅

- [x] 新增用户入口数据结构（`POST/GET /auth/users` + migration 008）
- [x] UI 暂时仍只开放导演账号（`uiEnabled` 门禁 + 登录页固定 director）
- [x] Session / Token 规范化（`authsessionentity` + Bearer / X-Session-Token）
- [x] LLM Key 加密入库（`secret_vault` + migration 009，`APP_SECRET_KEY`）

### Sprint 8 — P2 增强（按需排期）

- [x] 业务校验四件套（时长偏差 / 未绑定素材 / 地点跳切 / 导出主题一致，见 §6.1）
- [x] 导出格式与预览增强（CSV、校验摘要、复制预览，见 §6.2）
- [x] **BGM 推荐工作流**：LLM 推荐真实歌名 → 选定 → 下载上传 → 识别；未完成则分镜锁定（migration 011）
- [x] 交互统一（见 §6.3）→ **Sprint 9 ✅**
- [ ] 视频内容分析 / 素材自动标签（远期）→ **移出二期，见 §10.3**
- [ ] 自动粗剪结构准备（不做完整成片）→ **Sprint 10 仅文档评估**

### Sprint 9 — 交互统一 + 清单对齐（二期收尾 A） ✅

**目标**：把剩余 P2 交互债收干净，同步过时勾选，形成可验收的 UI 口径。

- [x] **列表 ↔ 编辑模式统一**
  - 素材 / 主题 / 分镜：统一「列表页操作区 + 行内状态 + 编辑入口」布局
  - 保存 / 取消 / 删除：统一 BlockingNotice + ToastNotice + ConfirmDialog
  - 空态、加载态、错误态与 rhythm / export 页对齐（`EmptyState` / `InlineErrorBanner`）
- [x] **复杂选择器体验**
  - 分镜编辑页素材选择：按 `location` 分组 + 关键词过滤（`AssetSelector`）
  - 主题选择页：已选主题置顶与候选卡片视觉层级统一
  - 键盘：列表 Enter 进入编辑、Esc 取消（分镜 / 素材编辑页）
- [x] **时间类输入统一**
  - 抽 `TimeSecondsInput` + `lib/time-input.ts`：秒数输入、失焦校验、最小 0 / 最大目标时长
  - `storyboard-segment-editor-client` 与 `asset-form-prototype` 共用
  - 非法输入统一提示：「请输入有效秒数，例如 1.5」
- [x] **清单与文档对齐**
  - §5.3「LLM 二层排序」已勾选（Sprint 6 `merge_asset_order`）
  - §5.4 字幕写回已勾选；「完整脚本写回」标 Sprint 10 评估 / 三期
  - §4.3 长期方案见下方「数据结构长期方向」
- [x] **回归**
  - 新增 `regression-sprint9.md`；`verify-workflow.mjs` 同步 BGM analyzed 门禁（7 checks）

**验收标准**：导演账号走通全流程，时间输入行为一致，分镜素材选择可搜可分组，删除走 ConfirmDialog。

### Sprint 10 — 验收冻结 + 三期 backlog（二期收尾 B）

**目标**：正式关闭二期范围，未做能力写入 backlog，不做新大功能。

- [ ] **导出写回完整性（轻量）**
  - 评估导出 Markdown/JSON 是否需反向导入分镜字幕 / 标签（若成本高则只写评估结论）
  - 至少保证：LLM 导出建议 → `segmentCaptions` 写回已有回归覆盖
- [ ] **LLM 分镜建议可信度（ polish，非重构）**
  - Prompt / validation 联动：生成后若 `issues` 非空，LLM 结果页顶部固定展示校验摘要
  - 可选：分镜 LLM 失败时 meta 文案与主题 / 导出页完全一致（复用 `describeLlmStatus`）
- [ ] **§6.4 远期 AI — 仅评估文档**
  - 输出 `docs/phase3-backlog.md`（或 master 附录）：视频分析、自动标签、粗剪结构、OAuth 实装
  - **不**在本 Sprint 写识别/粗剪代码
- [ ] **二期验收清单**
  - `phase2-checklist.md` 全部 P0/P1 勾选或显式标「移出二期」
  - `phase2-master.md` 状态改为「二期已关闭」
  - README / 部署说明补：`APP_SECRET_KEY`、migration 010、导演 re-login 说明
- [ ] **全量回归**
  - `pytest tests/ -q` + LLM 子集 + workflow 脚本
  - 手工 smoke：登录 → 建项（路线可选、地点校验开关）→ 导出 CSV

**验收标准**：文档声明二期 closed；§6.3 完成；§6.4 / OAuth / 视频分析明确在三期 backlog。

## 4. P0 必做项

### 4.1 文档与编码统一

- [x] 全部核心文档统一为 UTF-8
- [x] 避免 PowerShell / 编辑器编码不一致导致再次污染
- [x] 后续新增文档沿用当前编码规范

### 4.2 服务分层整理

- [x] 继续拆分 `repository` 中的生成型逻辑
- [x] 将节奏、主题、分镜、导出建议逐步下沉到独立 service
- [x] 形成清晰的“数据访问 / 规则生成 / LLM 调用”三层边界

### 4.3 数据结构与迁移规范

- [x] 明确数据库 schema 变更流程（`schemaversionentity` + 编号 migration）
- [x] 每次新增字段都同步 migration、schema、api 文档（SOP 见 `schema-migration.md` §6）
- [ ] 给音频分析、登录用户、LLM 配置相关数据结构补长期方案 → **Sprint 9 文档段（见下）；实现已落地 migration 008/009/011**

#### 数据结构长期方向（Sprint 9 文档对齐）

| 领域 | 当前态（二期） | 三期方向 |
|------|-------------|---------|
| **音频 / BGM** | 用户下载上传 BGM → librosa 识别节拍；`recommended_bgm` / `bgm_phase` 工作流 | 可选接入音乐平台 API 预览；多轨 / 版权元数据；识别结果缓存与增量重分析 |
| **Session / 用户** | SQLite `authsessionentity` + Bearer Token；导演 / 剪辑角色；用户表 `uiEnabled` 门禁 | Redis 会话、Refresh Token、完整 RBAC、剪辑侧独立 LLM 配额 |
| **LLM 配置** | DB Provider 表 + `enc:v1:` API Key（migration 009）；导演专属设置页 | OAuth / Device Code 实装；按项目/用户级模型路由；调用审计与成本统计 |

### 4.4 基础稳定性

- [x] 继续排查工作流页面之间的可点击状态联动问题
- [x] 统一成功提示、加载提示、错误提示口径
- [x] 关键操作补最小回归检查（见 `regression-sprint3.md`）

## 5. P1 优先功能项

### 5.1 音频上传与节拍识别

- [x] 扩展音频格式支持，不只限于当前基础格式
- [x] 提高 beat point 识别质量（librosa 主识别 + 能量算法兜底）
- [x] 明确“规则生成”和“音频分析生成”的来源标记（含 rule_fallback）
- [x] 让节奏说明更好解释识别结果（BPM、时长、节拍点数量）
- [x] 识别失败时自动回退规则生成
- [x] 支持移除已绑定音频 / 重新上传时清理旧文件
- [x] 剪映踩点语义（踩节拍1 粗 / 踩节拍2 细 / 强弱拍）
- [x] 原始节拍缓存（`rawBeatPoints` / `coarseBeatPoints`）与模式切换重采点
- [x] 暗场建议基于音频能量结构（Sprint 4）
- [x] 剪映点位细/粗两档 onset（Sprint 4）
- [x] rhythmNotes / bgmStyle LLM 化（Sprint 4）

### 5.2 LLM 主题建议

- [x] 强化主题候选的可解释性（usedLocations / usedAssetIds）
- [x] 增加候选间差异度控制
- [x] 明确失败兜底和超时兜底策略（`regression-sprint5.md` §5 + 前端 `describeLlmStatus`）

### 5.3 LLM 分镜建议

- [ ] 在现有节奏、素材、主题基础上输出更可信的分镜建议 → **Sprint 10 polish（validation 摘要联动）**
- [x] 后续支持「大模型建议顺序」作为二层排序来源之一（`merge_asset_order`，Sprint 6）
- [x] 强化素材绑定和地点连续性校验（validation 文案 + 前端提示；地点顺序校验可选 `validateLocationOrder`）

### 5.4 LLM 导出建议

- [x] 让标题、标签、文案建议更贴近平台风格
- [x] 预留后续多平台差异化策略（platformGuide 结构）
- [x] 分镜字幕写回（`segmentCaptions` → subtitle，Sprint 6）
- [ ] 将最终导出结果更完整写回时间线脚本 → **Sprint 10 评估；完整反向导入标三期**

### 5.5 用户与鉴权

- [x] 将用户信息从前端代码迁移到后台数据库
- [x] 改为后端校验登录
- [x] 保留新增用户入口的数据结构（`POST /auth/users`，默认 uiEnabled=false）
- [x] UI 暂时仍可只开放导演账号

### 5.6 LLM Provider 与鉴权标准化

- [x] 建立 Provider Registry
- [x] 建立统一 Auth Service
- [x] 支持 API Key 配置
- [x] LLM 配置角色策略：仅导演可改，剪辑共用系统级 Provider（`/api/llm/*` + `/settings/llm`）
- [x] 预留 OAuth / Device Code 能力（stub 已留；**实装移三期**，见 §11.3）
- [x] 不支持通过抓取网页登录 Cookie 作为正式方案（边界声明，无需开发）

## 6. P2 增强项

### 6.1 更强业务校验

- [x] 检查分镜总时长与目标时长偏差（`durationDeltaSec` / `durationWithinTolerance`）
- [x] 检查未绑定素材的镜头（`unboundSegmentCount`）
- [x] 检查跨地点跳切风险（`issues` 含具体回跳描述）
- [x] 检查导出文案与主题一致性（`exportValidation`）

### 6.2 导出能力增强

- [x] 扩展导出内容结构（Markdown / JSON / YAML 含校验摘要）
- [x] 增加更多下载格式（CSV 分镜时间线）
- [x] 优化预览阅读体验（导出页校验面板、复制、字符数）

### 6.3 交互体验优化

- [x] 持续统一列表页与编辑页交互模式 → **Sprint 9**
- [x] 优化复杂选择器的搜索、分组、键盘操作 → **Sprint 9**
- [x] 保持所有时间类输入控件体验一致 → **Sprint 9**

### 6.4 AI 深化能力

- [ ] 引入更强的大模型分镜组织能力 → **三期 backlog（Sprint 10 只写评估）**
- [ ] 研究更合理的镜头复用策略，但不一定进入标准主流程 → **三期 backlog**
- [ ] 评估后续自动粗剪的结构准备 → **Sprint 10 文档评估，不写粗剪代码**

## 7. 二期边界（明确不做）

- 自动粗剪产出完整成片
- 重型素材管理平台
- 完整多角色协同权限体系
- 网页 Cookie 抓取式 LLM 登录

## 8. 关键路径最小回归清单（Sprint 3 ✅ + Sprint 5 ✅）

自动化脚本见 `regression-sprint3.md`（主流程）与 `regression-sprint5.md`（LLM / SSE）。

自动化脚本见 `regression-sprint3.md`。覆盖路径：

1. 后端启动 → migration 002/003 在旧库上成功升级
2. 登录 → 进入项目 → workspace 数据完整
3. 主题选定 → 节奏页 BGM 推荐 → 选定曲目 → 上传音频 → 识别节拍
4. 切换踩点模式 → 保存后点数变化正确
5. 识别失败场景 → `rule_fallback`、节拍清空、`bgmPhase` 保持 `recommended`
6. 删除音频 → 节拍清空、`bgmPhase` 回退 `recommended`
7. 生成分镜（规则 + LLM）→ 单镜头编辑 → 保存（需节奏已 analyzed）
8. 导出预览 Markdown / JSON / YAML / CSV

运行命令：

```powershell
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_llm_routes.py tests/test_llm_gateway.py tests/test_llm_model_catalog.py tests/test_llm_stream.py -q

cd ..
node scripts/verify-workflow.mjs
```

## 9. 推荐推进顺序

1. ~~Sprint 3~~：文档对齐 + 回归清单 + 字段变更 SOP ✅
2. ~~Sprint 4~~：节奏字段剩余升级 ✅
3. ~~Sprint 5~~：LLM Gateway 标准化 ✅
4. ~~Sprint 6~~：主题 / 分镜 / 导出 LLM 质量 ✅
5. ~~Sprint 7~~：用户鉴权收尾 ✅
6. ~~Sprint 8~~：P2 校验与导出增强 ✅
7. **Sprint 9**：交互统一 + 清单 / 文档对齐 ✅
8. **Sprint 10**：验收冻结 + 三期 backlog 文档
9. **二期关闭**：P0/P1 全部验收，§6.4 / 视频分析 / OAuth 实装移出

## 10. 二期未完成项汇总与处置（截至 2026-06-25）

### 10.1 必须在二期关闭前完成（Sprint 9～10）

| 项 | 来源 | Sprint | 工作量 |
|----|------|--------|--------|
| 列表 / 编辑 / 提示交互统一 | §6.3 | 9 | 中 | ✅ |
| 素材选择器搜索 + 分组 | §6.3 | 9 | 中 | ✅ |
| 分镜时间输入组件统一 | §6.3 | 9 | 小 | ✅ |
| 过时 checklist 勾选同步 | 多处 | 9 | 小 |
| §4.3 数据结构长期方案文档 | §4.3 | 9 | 小 |
| 分镜 LLM + validation 摘要联动 | §5.3 | 10 | 小 |
| 导出写回范围评估 | §5.4 | 10 | 小 |
| 二期验收 + 部署说明 | — | 10 | 小 |
| 全量回归 | §8 | 10 | 小 |

### 10.2 Sprint 5 遗留（明确不阻塞二期关闭）

| 项 | 处置 |
|----|------|
| OAuth / Device Code 实装 | 移 **三期**；当前 API Key 模式已满足 MVP |

### 10.3 移出二期（写入三期 backlog，Sprint 10 文档化）

| 项 | 原因 |
|----|------|
| 视频内容分析 / 素材自动标签 | 依赖模型与算力，超出二期「更稳工程结构」目标 |
| 自动粗剪产出 / 结构实装 | §7 边界明确不做完整成片 |
| 更强分镜组织 / 镜头复用策略 | 研究项，需单独 PRD |
| 导出脚本 → 分镜反向导入 | 可做三期「协作编辑」特性 |
| 完整多角色权限 | §7 边界不做 |

### 10.4 已实现但清单未勾（Sprint 9 一并勾选）

- §5.3 LLM 二层排序（`merge_asset_order`）
- §5.4 字幕写回（`segmentCaptions`）
- §5.6 Cookie 抓取不做（边界）
- Sprint 5 OAuth stub（预留即可）

## 11. 关联文档

- `phase1-context.md`
- `phase2-master.md`
- `phase2-llm-integration-standard.md`
- `prd.md`
- `sop.md`
- `api.md`
- `schema-migration.md`
- `regression-sprint3.md`
- `regression-sprint5.md`
