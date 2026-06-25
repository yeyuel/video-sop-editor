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
