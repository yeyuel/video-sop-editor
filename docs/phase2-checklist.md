# 二期执行清单

## 1. 文档目的

本文档用于把二期工作拆成可跟踪事项。优先级分为 `P0 / P1 / P2`，Sprint 按迭代推进；勾选状态请在开发过程中持续维护。

## 2. 当前状态概览（截至 2026-06-23）

| 阶段 | 状态 | 说明 |
|------|------|------|
| 一期主流程 | ✅ 已可用 | 新建 → 录入 → 主题 → 节奏 → 分镜 → 导出 |
| Sprint 1（P0 工程收口） | ✅ 已完成 | 服务拆分、migration 001、workflow 联动、提示统一 |
| Sprint 2（音频节拍） | ✅ 已完成 | librosa + 能量兜底、剪映踩点语义、rawBeatPoints、migration 002/003 |
| Sprint 3（P0 收尾 + 文档对齐） | ✅ 已完成 | 回归测试、字段变更 SOP、文档同步 |
| Sprint 4（节奏模块深化） | ✅ 已完成 | 暗场能量分析、细/粗踩点、LLM 节奏文案、曲名真实化 |
| LLM 孤立能力 | 🟡 已接入、待深化 | 主题 / 分镜 / 导出 LLM 待 Sprint 6 质量增强 |
| 二期系统化整理 | 进行中 | LLM 业务质量（Sprint 6）待推进 |

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

### Sprint 5 — LLM 网关标准化

- [x] Provider Registry（多厂商 base_url / model / timeout）
- [x] 统一 Auth Service（完善 API Key，预留 OAuth / Device Code）
- [x] LLM Gateway（超时、重试、JSON 解析失败、空响应兜底）
- [x] 前端区分 LLM 未配置 / 超时 / 解析失败 / 规则兜底
- [x] 配置管理长期方案（环境变量 → 可选 DB 配置表 migration 005）

### Sprint 6 — LLM 业务质量

**主题建议**

- [ ] 候选间差异度控制（情绪轴 / 叙事结构不重复）
- [ ] 可解释性：标注用了哪些素材 / 地点
- [ ] 失败兜底策略文档化 + 前端提示

**分镜建议**

- [ ] 结合 `rawBeatPoints` + 踩点模式做 beat 对齐切镜
- [ ] 地点连续性校验强化
- [ ] LLM 排序作为二层来源，保留规则排序兜底
- [ ] 「适配节拍」开关与 validation 结果联动

**导出建议**

- [ ] 按平台差异化标题、标签、文案风格
- [ ] 导出结果更完整写回时间线脚本

### Sprint 7 — 用户与鉴权

- [ ] 新增用户入口数据结构（API + 表结构预留）
- [ ] UI 暂时仍只开放导演账号
- [ ] Session / Token 规范化
- [ ] LLM Key 等敏感配置不入库明文（或加密方案）

### Sprint 8 — P2 增强（按需排期）

- [ ] 业务校验四件套（见 §5.1）
- [ ] 导出格式与预览增强（见 §5.2）
- [ ] 交互统一（见 §5.3）
- [ ] 视频内容分析 / 素材自动标签（远期）
- [ ] 自动粗剪结构准备（不做完整成片）

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
- [ ] 给音频分析、登录用户、LLM 配置相关数据结构补长期方案

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

- [ ] 强化主题候选的可解释性
- [ ] 增加候选间差异度控制
- [ ] 明确失败兜底和超时兜底策略

### 5.3 LLM 分镜建议

- [ ] 在现有节奏、素材、主题基础上输出更可信的分镜建议
- [ ] 后续支持“大模型建议顺序”作为二层排序来源之一
- [ ] 强化素材绑定和地点连续性校验

### 5.4 LLM 导出建议

- [ ] 让标题、标签、文案建议更贴近平台风格
- [ ] 预留后续多平台差异化策略
- [ ] 将最终导出结果更完整写回时间线脚本

### 5.5 用户与鉴权

- [x] 将用户信息从前端代码迁移到后台数据库
- [x] 改为后端校验登录
- [ ] 保留新增用户入口的数据结构
- [ ] UI 暂时仍可只开放导演账号

### 5.6 LLM Provider 与鉴权标准化

- [x] 建立 Provider Registry
- [x] 建立统一 Auth Service
- [x] 支持 API Key 配置
- [x] 预留 OAuth / Device Code 能力
- [ ] 不支持通过抓取网页登录 Cookie 作为正式方案

## 6. P2 增强项

### 6.1 更强业务校验

- [ ] 检查分镜总时长与目标时长偏差
- [ ] 检查未绑定素材的镜头
- [ ] 检查跨地点跳切风险
- [ ] 检查导出文案与主题一致性

### 6.2 导出能力增强

- [ ] 扩展导出内容结构
- [ ] 增加更多下载格式
- [ ] 优化预览阅读体验

### 6.3 交互体验优化

- [ ] 持续统一列表页与编辑页交互模式
- [ ] 优化复杂选择器的搜索、分组、键盘操作
- [ ] 保持所有时间类输入控件体验一致

### 6.4 AI 深化能力

- [ ] 引入更强的大模型分镜组织能力
- [ ] 研究更合理的镜头复用策略，但不一定进入标准主流程
- [ ] 评估后续自动粗剪的结构准备

## 7. 二期边界（明确不做）

- 自动粗剪产出完整成片
- 重型素材管理平台
- 完整多角色协同权限体系
- 网页 Cookie 抓取式 LLM 登录

## 8. 关键路径最小回归清单（Sprint 3 ✅）

自动化脚本见 `regression-sprint3.md`。覆盖路径：

1. 后端启动 → migration 002/003 在旧库上成功升级
2. 登录 → 进入项目 → workspace 数据完整
3. 主题选定 → 节奏页规则生成 → 保存
4. 上传音频 → 识别 BPM / 节拍点 → 切换踩点模式 → 保存后点数变化正确
5. 识别失败场景 → rule_fallback → 仍可保存
6. 删除音频 → 节拍数据保留、音频字段清空
7. 生成分镜（规则 + LLM）→ 单镜头编辑 → 保存
8. 导出预览 Markdown / JSON / YAML

运行命令：

```powershell
cd backend
python -m pytest tests/ -q

cd ..
node scripts/verify-workflow.mjs
```

## 9. 推荐推进顺序

1. ~~Sprint 3~~：文档对齐 + 回归清单 + 字段变更 SOP ✅
2. ~~Sprint 4~~：节奏字段剩余升级 ✅
3. **Sprint 5**：LLM Gateway 标准化
4. **Sprint 6**：主题 / 分镜 / 导出 LLM 质量
5. **Sprint 7**：用户鉴权收尾
6. **Sprint 8**：P2 增强与远期 AI 能力

## 10. 关联文档

- `phase1-context.md`
- `phase2-master.md`
- `phase2-llm-integration-standard.md`
- `prd.md`
- `sop.md`
- `api.md`
- `schema-migration.md`
- `regression-sprint3.md`
