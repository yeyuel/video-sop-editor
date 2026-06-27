# Sprint 13 回归清单 — 导出 ↔ 分镜反向导入

## 目标

Sprint 13：export JSON schema version、dry-run/apply 导入 API、冲突策略 UI、CSV 列映射导入、round-trip 测试。

## 自动化

```powershell
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_regression_sprint13.py tests/test_export_import.py -q

cd ../frontend
npm run test:unit

cd ..
node scripts/verify-workflow.mjs
```

## Sprint 13 专项

| 项 | 验证方式 |
|----|---------|
| JSON schemaVersion | `test_export_import.py::test_render_export_content_includes_schema_version` |
| dry-run 不写 DB | `test_regression_sprint13.py::test_import_export_json_dry_run_does_not_modify_storyboard` |
| apply 写回 subtitle | `test_regression_sprint13.py::test_import_export_json_apply_updates_subtitle` |
| round-trip segment id | `test_regression_sprint13.py::test_import_export_json_round_trip_preserves_segment_ids` |
| CSV 预览 | `test_regression_sprint13.py::test_import_export_csv_dry_run_preview` |
| 前端导入 UI | 导出页「反向导入分镜」区块 |

## 手工 smoke（可选）

1. 导出页预览 JSON → 下载
2. 修改 `storyboard[].subtitle` → 上传 → 预览 diff
3. 应用导入 → 分镜页字幕已更新

## 最近验证

- 日期：2026-06-21
- 结果：backend 121 passed；frontend vitest 5 passed；verify-workflow 7 checks
