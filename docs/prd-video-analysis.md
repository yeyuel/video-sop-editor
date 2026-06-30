# 视频 Vision 分析 PRD（Sprint 14）

## 目标

在素材编辑页，通过 LLM Vision 对视频抽帧分析，自动预填画面内容、镜头类型、情绪/视觉标签、信息量与建议时长，减少手工录入。

## 抽帧策略

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VISION_FRAME_INTERVAL_SEC` | 2.0 | 相邻采样点时间间隔（秒） |
| `VISION_MAX_FRAMES` | 6 | 最多发送帧数，控制 token 成本 |

依赖服务端已安装 `ffmpeg`。视频路径 = 项目 `mediaRoot` + 素材 `relativePath`。

## 支持 Provider

- **OpenAI / OpenAI Compatible**：`gpt-4o`、`gpt-4o-mini` 等
- **Google Gemini**：`gemini-2.0-flash`、`gemini-1.5-flash/pro`
- **Kimi (Moonshot)**：`kimi-k2.5`、`kimi-k2.6`（多模态）；`moonshot-v1-*` 不支持 Vision

Provider 与模型在 LLM 设置页配置；素材分析使用**当前生效 Provider**。

## 模型能力检测

1. 若 Provider 已配置 API Key，调用 `GET {baseUrl}/models` 实时获取模型列表
2. 解析 API 返回的 `modalities` / `capabilities` 等字段；无法解析时使用模型 ID 启发式规则
3. 结果缓存 1 小时（`AppSettingEntity`）
4. 前端在 LLM 设置与素材表单中，对不支持 Vision 的模型显示警告

## 输出字段

| 字段 | 类型 | 说明 |
|------|------|------|
| scene | string | 画面内容 |
| shotType | enum | wide / medium / subject_medium / close_up / human / animal / transition |
| emotionTags | string[] | 情绪标签 |
| visualTags | string[] | 视觉标签 |
| informationDensity | enum | low / medium / high |
| suggestedDurationSec | number | 建议时长（秒） |

## 失败策略

- LLM 未配置 / 模型不支持 Vision / 找不到视频 / ffmpeg 不可用：返回明确错误，**不阻断手工录入**
- 分析结果写入 `vision_analysis_json` + `vision_analysis_status`（empty / pending / ready / failed）
- 用户确认后保存素材，正式写入 tags 并清空预填状态

## 结果缓存

同一项目内，若另一素材已对**相同视频文件**完成 Vision 分析（`vision_analysis_status=ready`），则按文件 fingerprint 复用结果，跳过 ffmpeg 抽帧与 LLM 调用。

- 文件存在时：fingerprint = `path + mtime + size`（与媒体预览缓存一致）
- 文件暂不可访问时：fallback 为 `projectId + relativePath`（便于 mock / 离线录入场景）
- 缓存写入 `vision_analysis_json.fileFingerprint`；命中时 SSE 阶段 `cache_hit`

## 测试模式

设置 `VISION_USE_MOCK=true` 时跳过真实 API 与 ffmpeg，返回 fixture JSON（CI 使用）。

## API

- `GET /projects/{id}/assets/vision-capability` — 剪辑可见，检查当前模型 Vision 能力
- `POST /projects/{id}/assets/{assetId}/vision-analyze/stream` — SSE 进度 + 预填结果
- `GET /llm/providers/{id}/models?live=true` — 导演可见，实时模型列表（含 supportsVision）
- `GET /llm/vision-capability` — 导演可见，当前生效模型 Vision 能力
