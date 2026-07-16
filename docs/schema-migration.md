# 数据库迁移规范

## 1. 目标

为 SQLite schema 变更提供可追踪、可重复执行的迁移流程，避免继续在 `repository` 或启动脚本里散落 `ALTER TABLE`。

## 2. 机制

- 迁移入口：`app/migrations/runner.py` 中的 `run_migrations()`
- 兼容入口：`app/migrations/__init__.py` 导出 `run_migrations` / `run_sqlite_migrations`（供 `main.py` 调用）
- 版本表：`schemaversionentity(id, version)`
- 每次 schema 变更新增一个递增编号 migration

## 3. 新增 migration 步骤

1. 在 `MIGRATIONS` 列表末尾追加 `(version, name, fn)`
2. 在 `fn(session)` 内用 `inspect(engine)` 检查列是否存在，再执行 `ALTER TABLE`
3. 同步更新：
   - `app/models/entities.py`
   - `app/models/schemas.py`（如有 API 字段）
   - `docs/api.md`
   - `docs/schema-migration.md`（migration 列表）
   - 如涉及产品口径变化，同步 `docs/prd.md`
4. 本地验证：
   - 旧库升级：保留现有 `video_sop.db` 启动一次
   - 新库初始化：`del video_sop.db && python init_db.py`

## 4. 当前 migration 列表

| Version | Name | 说明 |
|---------|------|------|
| 1 | `001_legacy_columns` | 项目 media_root、style_notes、素材 relative_path、节奏音频字段 |
| 2 | `002_rhythm_analysis_metrics` | 节奏表 detected_bpm、audio_duration_sec |
| 3 | `003_rhythm_raw_beats` | 节奏表 raw_beat_points（细粒度节拍） |
| 4 | `004_rhythm_coarse_beats` | 节奏表 coarse_beat_points（粗粒度/强拍序列） |
| 5 | `005_llm_provider_config` | LLM Provider 配置表（provider_id、api_key、model 等） |
| 6 | `006_app_settings` | 应用级 KV 设置（如 `llm_active_provider_id`） |
| 7 | `007_theme_evidence` | 主题表 used_locations / used_asset_ids（可解释性） |
| 8 | `008_auth_sessions` | 会话表 authsessionentity + userentity.created_at |
| 9 | `009_encrypt_llm_api_keys` | LLM api_key 加密存储（enc:v1: 前缀） |
| 10 | `010_project_location_validation` | 项目表新增 `validate_location_order`（地点顺序校验开关，默认关闭） |
| 11 | `011_rhythm_bgm_recommendations` | 节奏表 `recommended_bgm`、`selected_bgm_id`、`bgm_phase`（BGM 推荐工作流） |
| 12 | `012_llm_call_logs` | LLM 调用审计日志表 |
| 13 | `013_asset_vision_analysis` | 素材 Vision 分析 JSON + status |
| 14 | `014_allow_asset_reuse` | 项目表 `allow_asset_reuse`（镜头复用开关，默认关闭） |
| 15 | `015_llm_oauth_and_openai_merge` | OAuth token 表 + pending state；`openai-compatible` → `openai` |
| 16 | `016_subscription_oauth` | 订阅型 OAuth / device flow 所需字段与 token 表结构升级 |
| 17 | `017_project_jianying_draft_root` | 项目表新增 `jianying_draft_root` |
| 18 | `018_phase4_rhythm_profile` | 节奏表新增 `rhythm_profile_json`、`attention_beats_json`、`beat_calibration_json`、`audio_fingerprint`、`audio_analysis_version` |
| 19 | `019_phase4_storyboard_segment_roles` | 分镜表新增 `attention_role`、`visual_strength`、`motion_policy`、`transition_policy` |
| 20 | `020_storyboard_selection_trace` | 分镜表新增素材选择与排序追溯信息 |
| 21 | `021_project_duration_fill_max_consecutive_route` | 项目新增同一地点连续补齐镜头上限 |
| 22 | `022_storyboard_voiceover_fields` | 分镜新增口播文案、角色与时间策略 |
| 23 | `023_export_voiceover_script` | 导出方案新增整段口播稿 |
| 24 | `024_export_voiceover_settings` | 导出方案新增 Provider、风格、语速与情绪配置 |
| 25 | `025_export_voiceover_generation_state` | 导出方案新增口播音频生成状态和元数据 |
| 26 | `026_export_voiceover_density` | 导出方案新增口播密度配置 |
| 27 | `027_storyboard_subtitle_policy` | 分镜新增字幕样式策略 |
| 28 | `028_export_voiceover_voice` | 导出方案新增 `voiceover_voice`，保存 Edge TTS 音色选择 |
| 29 | `029_llm_result_cache` | 新增 `llmresultcacheentity`，按输入指纹持久化成功的 LLM JSON 结果及命中次数 |
| 30 | `030_llm_background_tasks` | 新增 `llmtaskentity`，持久化 LLM 后台任务状态、进度、结果和取消标记 |
| 31 | `031_rough_cut_versions` | 新增 `roughcutversionentity`，保存一键初剪的结构化方案快照、生成模式及 Provider/模型信息 |

## 5. 注意事项

- SQLite 不支持删除列，废弃字段只能留空或重建表
- migration 必须幂等（重复执行不报错）
- 不要提交 `video_sop.db` 和 `backend/storage/` 下的媒体文件

## 6. 字段变更检查清单

每次新增或修改 API 字段时，按顺序核对：

- [ ] `app/migrations/runner.py` 追加 migration（幂等 `ALTER TABLE`）
- [ ] `app/models/entities.py` 实体字段
- [ ] `app/models/schemas.py` Read / Write schema
- [ ] `docs/api.md` 请求 / 响应示例
- [ ] `docs/schema-migration.md` migration 列表
- [ ] 前端 `types/domain.ts` 与相关组件（如有）
- [ ] 本地验证：旧库升级 + 新库初始化
