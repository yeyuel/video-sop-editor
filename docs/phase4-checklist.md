# Phase 4 执行清单

## 1. 阶段目标

四期目标是提升自动初剪质量，而不是扩张协作和资产管理范围。

主线优先级：

1. 自动粗剪质量提升
2. 平台化节奏模型
3. 剪映节拍对齐优化
4. LLM 性能与稳定性
5. 轻量部署与数据存储评估

当前阶段（2026-07-16）：

- P4-A 自动粗剪质量主线已完成当前范围并通过回归。
- P4-B 自动口播、LLM 后台任务、结果缓存及一键初剪双模式已完成。
- 一键初剪支持“补齐缺失阶段”和“从头生成创意方案”；后者保留真实音频节拍，并保存 Provider/模型版本快照。
- 下一阶段聚焦单步骤/局部重跑、历史版本差异与恢复；P4-C 部署和存储评估尚未启动。

## 2. P4-A：自动粗剪质量主线

P4-A 只做会直接影响节奏、分镜和剪映草稿质量的能力。自动口播、完整 LLM 后台任务、一键初剪和部署评估放到 P4-B / P4-C。

### Sprint 19A：平台节奏画像与 attention beats

- [x] 定义 `rhythmProfile` schema
- [x] 定义 `attentionBeats` schema
- [x] 增加平台节奏模式：`highlight_reel`
- [x] 增加平台节奏模式：`seed_and_guide`
- [x] 增加平台节奏模式：`chapter_explainer`
- [x] 增加平台节奏模式：`emotional_vlog`
- [x] 增加平台节奏模式：`stable_story`
- [x] 节奏生成逻辑接入 `platform + videoType + targetDurationSec`
- [x] 节奏页区分展示音乐节拍点和内容注意力点
- [x] 分镜生成读取 `attentionBeats`
- [x] 更新 `prd.md`
- [x] 更新 `api.md`
- [x] 增加回归测试

验收：

- [x] 抖音 60 秒项目生成 4 个左右注意力节点
- [x] B 站攻略项目生成章节节点
- [x] 同一批素材在不同平台下生成不同节奏结构

### Sprint 20A：剪映节拍对齐优化

- [x] 梳理当前 `librosa` / 能量检测 / 剪映模式之间的差异
- [x] 定义 `beatCalibration` schema
- [x] 增加整体节拍偏移 `beatOffsetSec`
- [x] 增加节拍密度校准策略
- [x] 支持用户手动输入剪映参考节拍点
- [x] 支持根据参考点计算 offset
- [x] 支持根据参考点计算 scale
- [x] 支持根据参考点计算 density
- [x] 节奏页展示原始识别点、校准点、当前输出点
- [x] 分镜生成使用校准后的节拍点
- [x] 保存音频 fingerprint 和分析版本
- [x] 同一音频重新上传时复用校准数据
- [x] 更新 `api.md`
- [x] 增加音频节拍校准测试

验收：

- [x] 用户可以手动微调节拍点整体前后偏移
- [x] 用户可以用少量剪映参考点校准系统节拍点
- [x] 校准后分镜切点使用校准结果

### Sprint 21A：节点驱动分镜编排

- [x] 输出路线主轴与叙事骨架编排技术方案（见 `docs/narrative-storyboard-planning.md`）
- [x] 定义 `attentionRole`
- [x] 定义规则推断版 `visualStrength`
- [x] `visualStrength` 先基于 `shotType`、`informationDensity`、`functionTags`、`emotionTags`、`visualTags` 推断
- [x] 分镜生成 prompt 接入平台节奏画像
- [x] 规则生成接入平台节奏画像
- [x] 强视觉素材优先放入钩子、反转、高潮位
- [x] B 站攻略类优先章节化组织
- [x] 短视频类优先前 3 秒钩子和高频注意力点
- [x] 分镜列表展示注意力角色
- [x] 分镜编辑页支持修改注意力角色
- [x] 更新 `prd.md`
- [x] 增加分镜编排测试

验收：

- [x] 分镜能说明每段的叙事功能
- [x] 分镜不再只是按素材顺序平均铺开
- [x] 平台差异能反映到分镜结构上

### Sprint 22A：粗剪效果增强

- [x] 定义 `transitionPolicy`
- [x] 定义 `motionPolicy`
- [x] 定义字幕策略字段
- [x] 预留口播字段
- [x] 剪映草稿导出支持基础转场策略
- [x] 剪映草稿导出支持照片动效策略
- [x] 剪映草稿导出支持 BGM fade in / fade out
- [x] 剪映草稿导出支持关键节点字幕策略
- [x] 更新 `rough-cut-export.md`
- [x] 增加剪映导出回归测试

验收：

- [x] 导出的剪映草稿比当前版本包含更多可执行编辑信息
- [x] 视频、字幕、音频轨道结构清晰
- [x] 无 BGM 或无照片素材时不会阻断导出

### P4-A 技术债随业务偿还

- [ ] 修改节奏相关代码时，逐步拆分音频分析、节拍校准和节奏画像逻辑
- [ ] 修改分镜相关代码时，逐步降低 `repository.py` 的业务编排负担
- [ ] 修改导出相关代码时，统一剪映草稿字段映射和测试 fixture
- [x] P4-A 结束同步 `api.md`、`prd.md`、`schema-migration.md`

## 3. P4-B：生成体验与自动化增强

P4-B 在 P4-A 基础稳定后启动，主要解决口播、LLM 稳定性和一键化体验。

### Sprint 22B：自动口播与旁白音轨

- [x] 定义 `voiceoverProvider` 配置结构
- [x] 定义 `voiceoverText`
- [x] 定义 `voiceoverStyle`
- [x] 定义 `voiceoverSpeed`
- [x] 定义 `voiceoverEmotion`
- [x] 定义 `voiceoverTiming`
- [x] 支持根据分镜字幕生成逐镜头口播
- [x] 支持根据导出文案生成整段旁白
- [x] 支持用户手动输入固定口播稿
- [x] 生成并保存口播音频文件（Edge TTS MP3）
- [x] 保存 `voiceoverAudioPath`、`durationSec`、`providerMeta`
- [x] 前端支持试听口播
- [x] 前端支持重新生成口播
- [x] 前端支持删除口播音频
- [x] 剪映草稿导出支持 voiceover 音轨
- [x] BGM 与口播同时存在时自动降低 BGM 音量
- [x] 无 TTS Provider 配置时不阻断原有流程
- [x] 更新 `api.md`
- [x] 更新 `rough-cut-export.md`
- [x] 增加口播生成回归测试

验收：

- [x] 当前分镜字幕可生成口播音频
- [x] 导出文案可生成完整旁白音频
- [x] 剪映草稿包含 voiceover 音轨
- [x] 不做未授权声音克隆

### Sprint 23B：LLM 性能与稳定性

- [x] 定义 LLM 任务状态模型
- [x] LLM 长任务支持后台状态轮询
- [x] 支持任务取消、SSE 断线后自动轮询恢复，以及服务重启后的中断识别
- [x] 支持页面刷新恢复
- [ ] 支持所有独立生成入口的失败任务原参数一键重试
- [x] 增加输入 fingerprint 缓存
- [x] 拆分结构生成和文案生成 prompt：分镜阶段只负责结构，导出阶段统一生成字幕与发布文案
- [ ] Codex / OAuth 掉线时保留上下文
- [x] LLM 失败后明确展示 fallback 状态
- [x] 更新 LLM 接入文档
- [x] 增加任务状态查询和断线恢复基础测试

验收：

- [x] 页面刷新后能恢复 LLM 任务状态
- [x] 相同输入可复用缓存或提示无需重复生成
- [x] LLM 失败不阻断主工作流

### Sprint 24B：一键初剪方案

- [x] 新增项目概览一键生成入口
- [x] 串联主题生成与自动选择首个候选主题
- [x] 串联 BGM 推荐，并在未上传真实音频时安全暂停
- [x] 节拍分析就绪后串联分镜生成
- [x] 串联导出建议
- [x] 已有人工分镜和导出文案默认保留，不自动覆盖
- [x] 支持从头重新生成主题、分镜和导出文案
- [x] 重新生成前保存结构化方案快照，并标记 Provider 与模型
- [x] 重新生成时复用已上传音频、节拍识别和人工校准
- [ ] 支持单步骤重跑
- [ ] 支持局部段落重跑
- [ ] 支持在页面中查看差异并恢复指定历史版本（版本数据已落库）
- [x] 增加一键初剪后台任务端到端测试

验收：

- [ ] 新项目录入素材后可一键生成完整初剪方案
- [x] 用户仍可逐步进入每个阶段微调

### P4-B 技术债随业务偿还

- [x] 修改 LLM 相关代码时，统一任务状态、缓存和 fallback 表达
- [x] 修改口播相关代码时，统一 Provider 配置、音频文件存储和剪映音轨映射
- [x] P4-B 当前范围同步 `api.md`、`prd.md`、`schema-migration.md`

## 4. P4-C：部署与存储评估

- [ ] 评估 10 用户同时在线下 SQLite 可用边界
- [ ] 评估 Postgres 切换成本
- [ ] 评估对象存储接入时机
- [ ] 评估音频、关键帧、预览文件和剪映草稿存储策略
- [ ] 评估后台任务队列是否必要
- [ ] 输出部署建议文档

## 5. 开发顺序建议

1. 先做 Sprint 19A + 20A：节奏画像和剪映节拍校准。
2. 再做 Sprint 21A：节点驱动分镜。
3. 再做 Sprint 22A：剪映草稿基础效果增强。
4. P4-A 验收通过后，再进入 P4-B 的口播、LLM 后台任务和一键初剪。
5. P4-C 等真实上线前再启动，避免过早引入部署复杂度。
## 当前补充：整段口播稿文本链路

- [x] `ExportPlan` 新增 `voiceoverScript`，用于保存整段口播稿文本
- [x] `ExportPlan` 新增 `voiceoverProvider`、`voiceoverStyle`、`voiceoverSpeed`、`voiceoverEmotion`
- [x] `ExportPlan` 新增 `voiceoverVoice`，Edge TTS 支持智能匹配与常用中文男女声
- [x] 导出页支持用户手动输入固定口播稿
- [x] 导出页支持根据标题、标签和文案生成整段口播稿草稿
- [x] 导出页支持维护口播 Provider、风格、语速和情绪配置
- [x] 导出页支持检查口播生成配置并估算旁白时长
- [x] 保存 `voiceoverAudioPath`、`durationSec`、`providerMeta` 的结构占位
- [x] 支持 `mock_silence` 本地占位 WAV，验证生成、下载、试听和删除链路
- [x] 后端提供口播 Provider 能力表，前端不再单独判断 Provider 是否可用
- [x] 口播稿预览优先输出整段口播稿，再输出逐镜头口播
- [x] `mock_silence` 生成并保存与分镜时间线等长的本地占位静音 WAV
- [x] `jianying_native_tts` 支持剪映原生朗读交接：导出草稿时写入统一的“最终字幕（剪映朗读源）”文本轨
- [x] 接入 Edge TTS，生成并保存真实 MP3 口播音频文件
- [x] Edge TTS 与最终字幕共用压缩文本，并按真实发音边界生成同步字幕轨
- [x] 剪映草稿导出支持 voiceover 音轨
- [x] 剪映草稿导出支持原生朗读文本轨

## 6. 当前验证基线

- [x] 后端一键初剪、LLM、分镜、口播及剪映导出组合回归：93 项通过
- [x] 一键初剪双模式专项测试：2 项通过
- [x] 前端 Next.js 生产构建通过
- [x] Python 语法检查与 `git diff --check` 通过
