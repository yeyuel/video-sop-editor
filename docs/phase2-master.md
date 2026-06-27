# 二期开发主控文档

## 1. 文档目标

本文档作为二期总控入口，用于统一说明二期开发的目标、边界、优先级和实施顺序。后续开发、测试、验收默认以本文档为总览，以 `phase2-checklist.md` 为执行清单。

## 2. 当前项目所处阶段

截至 **2026-06-26**：

- 一期主工作流已经可以完整跑通
- **Sprint 1～10 已完成**，**二期已关闭**
- 新能力规划见 [`phase3-backlog.md`](phase3-backlog.md)
- 执行清单见 `phase2-checklist.md` §3 Sprint 1～10、§10 未完成项汇总

## 3. 一期基线能力

当前系统已经具备以下基线：

- 项目、素材、主题、节奏、分镜、导出的完整页面流
- 项目与素材 CRUD
- 主题生成与选定
- BGM 推荐 → 上传 → 节拍识别 → 分镜门禁
- 分镜生成、编辑、插入、删除、排序
- 导出预览与下载（Markdown / JSON / YAML / CSV）
- Session 登录与用户 API 预留
- LLM 主题 / 分镜 / 导出 / BGM 建议 + 规则兜底

## 4. 一期基线业务口径

二期开始前，以下口径视为一期既定事实，不再轻易改动：

- 工作流顺序为：新建 → 录入 → 主题 → 节奏 → 分镜 → 导出
- 分镜生成优先参考节奏模块的节拍点
- 一期不支持策略性复用同一素材来补齐时长
- 如确需复用同一源素材，临时方案是人工先切分为多个素材再录入
- 当前分镜排序为“功能标签阶段优先 + 同标签内按素材录入顺序”
- 项目目标时长最小值为 5 秒

## 5. 二期目标

二期核心目标不是重做一期，而是在一期稳定工作流上增强三类能力：

1. 更真实的输入
2. 更智能的建议
3. 更稳的工程结构

对应落地方向：

- 音频上传与真实节拍识别 + BGM 推荐工作流
- LLM 主题、分镜、导出建议深化
- 用户与鉴权体系后端化
- 数据结构与服务分层进一步规范
- 自动化校验与测试补齐
- 交互体验统一（Sprint 9）

**上述 P0/P1/P2 目标已达成**；二期正式关闭。

## 6. 二期边界

二期仍然不做以下内容（已写入三期 backlog，见 `phase3-backlog.md`）：

- 自动粗剪产出完整成片
- 高复杂度镜头复用策略引擎
- 多角色协同权限体系完整版
- 重型媒体资产管理平台
- 视频内容分析 / 素材自动标签
- OAuth / Device Code 实装（API Key 已满足 MVP）
- 网页 Cookie 抓取式 LLM 登录
- 导出 Markdown/JSON 全量反向导入

## 7. 当前优先级

### 已完成（Sprint 1～10）

- P0 工程收口、migration 规范、回归清单
- P1 音频节拍、LLM 全链路、鉴权、Key 加密、BGM 推荐
- P2 业务校验四件套、CSV 导出、交互统一、验收冻结

### 三期（新立项入口）

见 [`phase3-master.md`](phase3-master.md) 与 [`phase3-checklist.md`](phase3-checklist.md)。已锁定：剪辑开放、LLM Vision、镜头复用开关、OpenAI/Google OAuth、单机 SQLite。

## 8. 已落地的主要能力

- 音频上传 + librosa / 能量兜底节拍分析
- LLM 主题 / 分镜 / 导出 / BGM 推荐（Gateway + 规则兜底 + SSE）
- LLM Provider 配置页、激活与连通性测试（导演专属）
- Session Token 鉴权、用户 API、Fernet Key 加密
- 分镜 / 导出校验、`validateLocationOrder` 可选开关
- 分镜 validation 摘要面板、导出字幕写回

## 9. LLM 统一接入原则

二期 LLM 能力统一遵循以下原则：

- 不绑定单一厂商命名
- 优先支持 API Key 模式
- 允许后续接入 OAuth / Device Code（三期）
- 不依赖浏览器 Cookie 注入或抓取网页登录态
- Provider 配置、鉴权逻辑、模型调用逻辑分层处理

详细规范见 `phase2-llm-integration-standard.md`。

## 10. 执行顺序（归档）

1. Sprint 1～10 ✅
2. 二期关闭 ✅
3. 三期从 `phase3-backlog.md` 排期

## 11. 二期关闭标准（已满足）

1. `phase2-checklist.md` §6.3 三项完成 ✅
2. §10.1 表格内 Sprint 10 任务全部勾选 ✅
3. `pytest` 全绿 + `verify-workflow.mjs` 通过 ✅
4. §10.3 能力已写入 `phase3-backlog.md` ✅
5. 部署说明含 `APP_SECRET_KEY`、migration 011、re-login / Key 重配提示 ✅

**状态：二期已关闭（2026-06-26）**

## 12. 与其他文档的关系

- 看一期现状：`phase1-context.md`
- 看执行清单：`phase2-checklist.md`
- 看产品需求：`prd.md`
- 看标准流程：`sop.md`
- 看接口约束：`api.md`
- 三期 backlog：`phase3-backlog.md`
- Sprint 10 回归：`regression-sprint10.md`
