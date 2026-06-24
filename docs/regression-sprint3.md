# Sprint 3 回归测试说明

## 1. 目的

覆盖 `phase2-checklist.md` §8 关键路径，作为 P0 最小回归检查的可重复脚本。

## 2. 后端 API / 服务回归

在 `backend/` 目录执行：

```powershell
pip install -r requirements.txt
python -m pytest tests/ -q
```

`tests/test_regression_sprint3.py` 覆盖：

| # | 路径 | 测试用例 |
|---|------|----------|
| 1 | migration 002/003 旧库升级 | `test_migration_003_upgrades_legacy_rhythm_table`、`test_run_all_migrations_from_zero`、`test_migrations_idempotent` |
| 2 | 登录 + workspace | `test_login_and_workspace_unlock_steps` |
| 3 | 规则生成节奏 + 保存 | `test_rhythm_rule_generate_and_save` |
| 4 | 音频识别 + 踩点模式重采点 | `test_audio_upload_and_delete_audio`、`test_rhythm_beat_mode_refilter_on_save` |
| 5 | 识别失败 rule_fallback | `test_rule_fallback_on_invalid_audio` |
| 6 | 删除音频保留节拍 | `test_audio_upload_and_delete_audio` |
| 7 | 分镜生成 + 单镜头编辑 | `test_storyboard_generate_rule_and_llm_fallback`、`test_storyboard_segment_update` |
| 8 | 导出 Markdown / JSON / YAML | `test_export_markdown_json_yaml` |

另含单元测试：

- `tests/test_beat_grid.py` — 剪映踩点语义
- `tests/test_audio_analysis.py` — librosa / 能量识别

## 3. 前端 workflow 解锁逻辑

在项目根目录执行：

```powershell
node scripts/verify-workflow.mjs
```

验证 rhythm → storyboard 解锁依赖 `beatPoints.length > 0`。

## 4. 手动抽检（可选）

自动化未覆盖的 UI 交互建议偶尔手动确认：

- 节奏页切换踩节拍1/2 后 textarea 点数即时变化
- workflow stepper 各步高亮与跳转

## 5. 最近验证

- 日期：2026-06-23
- 结果：backend 17 passed；workflow script 5 checks passed
