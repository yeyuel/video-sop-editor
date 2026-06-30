# Sprint 14 回归清单 — LLM Vision 素材预填

## 后端

- [x] migration 013：`vision_analysis_json`、`vision_analysis_status`
- [x] `GET /llm/providers/{id}/models?live=true` 返回 `supportsVision`
- [x] `GET /llm/vision-capability` 与 `GET /projects/{id}/assets/vision-capability`
- [x] Kimi k2.5/k2.6 推断为 Vision；moonshot-v1 为否
- [x] Google Gemini Provider 已注册
- [x] `POST .../vision-analyze/stream` SSE + mock 模式（`VISION_USE_MOCK=true`）
- [x] 视频文件 fingerprint 缓存（同文件跳过重复 Vision 调用）

## 前端

- [x] LLM 设置：模型列表 Vision 标记 + 非 Vision 模型警告
- [x] 素材编辑：AI 分析按钮 + 预填高亮 + 失败 banner
- [x] Vision 分析 `LlmProgressOverlay` 阶段进度
- [x] 录入页连续录入（扫描 session + 保存跳下一条）

## 命令

```powershell
cd backend
python -m pytest tests/test_model_capabilities.py tests/test_regression_sprint14.py tests/test_vision_analysis.py -q
python -m pytest tests/ -q
```

## 验收

Mock 模式下分析样例素材 → ≥3 字段预填 → 同 `relativePath` 第二素材命中缓存 → 人工修改 → 保存成功。
