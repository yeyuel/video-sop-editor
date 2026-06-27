# Sprint 10 回归清单 — 二期验收冻结

## 目标

确认二期关闭标准：分镜 validation 摘要、导出字幕写回、文档与部署说明、全量自动化回归。

## 自动化

```powershell
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_llm_routes.py tests/test_llm_gateway.py tests/test_llm_model_catalog.py tests/test_llm_stream.py -q
python -m pytest tests/test_regression_sprint10.py -q

cd ..
node scripts/verify-workflow.mjs
```

## Sprint 10 专项

| 项 | 验证方式 |
|----|---------|
| 分镜 LLM 后校验摘要 | 生成分镜后列表页顶部 `校验摘要` 面板展示 `validation.issues` |
| 导出字幕写回 | `test_regression_sprint10.py::test_export_suggest_writes_segment_captions` |
| LLM meta 文案 | 分镜 / 主题 / 导出失败时 Toast 复用 `describeLlmStatus` |
| 三期 backlog | `docs/phase3-backlog.md` 含 §6.4 / OAuth / 视频分析 |

## 手工 smoke

1. 登录导演账号（若升级后 LLM Key 无法解密，需 re-login 或重置 Provider 配置）
2. 新建项目：路线选填、`validateLocationOrder` 开关可保存
3. 主题 → BGM 推荐 → 上传 → 分镜 → 导出 CSV
4. 分镜页：LLM 建议后查看校验摘要；导出页 LLM 建议后分镜字幕更新

## 部署检查

- [ ] `APP_SECRET_KEY` 已在生产 `.env` 配置（LLM Key 加密依赖）
- [ ] 旧库启动 migration 011 成功
- [ ] `ffmpeg` 可用（非 WAV 音频上传）
