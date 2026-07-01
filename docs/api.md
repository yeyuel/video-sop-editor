# API 文档 v1.1

Base URL:

`/api/v1`

返回格式统一：

```json
{
  "success": true,
  "data": {},
  "meta": {
    "requestId": "local-dev"
  }
}
```

## 0. 鉴权

### 0.1 登录

`POST /auth/login`

请求体：

```json
{
  "username": "director",
  "password": "root123"
}
```

响应 `data`：

```json
{
  "user": {
    "id": "user_director",
    "username": "director",
    "displayName": "Director",
    "role": "director",
    "uiEnabled": true
  },
  "sessionToken": "<opaque-token>",
  "expiresAt": "2026-06-21T12:00:00+00:00"
}
```

### 0.2 当前用户

`GET /auth/me`

请求头（二选一）：

- `Authorization: Bearer <sessionToken>`
- `X-Session-Token: <sessionToken>`

### 0.3 登出

`POST /auth/logout`

同上 Session Token 请求头；服务端撤销会话。

### 0.4 用户管理（导演专用，预留）

`GET /auth/users` — 列出用户（不含密码）

`POST /auth/users` — 创建用户（默认 `uiEnabled=false`，导演可登录）

请求体：

```json
{
  "username": "editor_a",
  "password": "secret12",
  "displayName": "剪辑 A",
  "role": "editor",
  "uiEnabled": false
}
```

## 1. 项目

## 1.1 获取项目列表

`GET /projects`

## 1.2 创建项目

`POST /projects`

请求体：

```json
{
  "name": "阿勒泰雪国片",
  "destination": "阿勒泰",
  "platform": "xiaohongshu",
  "targetDurationSec": 60,
  "videoType": "emotion_film",
  "stylePreference": "情绪氛围片",
  "routeText": "将军山 - 喀纳斯 - 禾木",
  "validateLocationOrder": false,
  "allowAssetReuse": false,
  "mediaRoot": "D:\\素材库\\阿勒泰项目",
  "status": "draft"
}
```

## 1.3 获取单个项目

`GET /projects/{projectId}`

## 1.4 更新项目

`PUT /projects/{projectId}`

## 1.5 删除项目

`DELETE /projects/{projectId}`

## 1.6 获取项目工作台数据

`GET /projects/{projectId}/workspace`

返回字段：

- `project`
- `assets`
- `themes`
- `storyboard`
- `storyboardValidation`
- `exportValidation`
- `rhythmPlan`
- `exportPlan`

## 2. 素材

## 2.1 获取素材列表

`GET /projects/{projectId}/assets`

## 2.2 创建素材

`POST /projects/{projectId}/assets`

请求体：

```json
{
  "location": "喀纳斯",
  "scene": "蓝冰河流特写，前景带雪面纹理",
  "relativePath": "喀纳斯/drone/KANAS_001.mp4",
  "mediaType": "drone_video",
  "shotType": "subject_medium",
  "emotionTags": ["冷", "静"],
  "visualTags": ["冷蓝", "白雪"],
  "informationDensity": "medium",
  "suggestedDurationSec": 1.5,
  "functionTags": ["slow_climax"]
}
```

说明：

- `assetId` 不需要前端传，后端自动生成

## 2.3 获取单条素材

`GET /projects/{projectId}/assets/{assetId}`

## 2.4 更新素材

`PUT /projects/{projectId}/assets/{assetId}`

## 2.5 删除素材

`DELETE /projects/{projectId}/assets/{assetId}`

## 3. 主题

## 3.1 获取主题列表

`GET /projects/{projectId}/themes`

## 3.2 生成主题

`POST /projects/{projectId}/themes/generate`

请求体：

```json
{
  "count": 3
}
```

## 3.3 选择当前主题

`PUT /projects/{projectId}/themes/select`

请求体：

```json
{
  "themeId": "theme_xxx"
}
```

## 4. 节奏规划

节奏页采用 **BGM 推荐 → 选定曲目 → 下载上传 → 音频识别** 流程。进入分镜前必须完成 BGM 推荐、曲目选定与音频识别（`bgmPhase === "analyzed"`）。

`bgmPhase` 取值：

- `empty`：尚未推荐 BGM
- `recommended`：已有 LLM 推荐列表（可能已选定曲目，但未完成音频识别）
- `analyzed`：已上传 BGM 并完成节拍识别

## 4.1 获取节奏规划

`GET /projects/{projectId}/rhythm-plan`

响应含 `recommendedBgm`、`selectedBgmId`、`bgmPhase` 等字段。

## 4.2 LLM 推荐 BGM

`POST /projects/{projectId}/rhythm-plan/bgm-recommend`

`POST /projects/{projectId}/rhythm-plan/bgm-recommend/stream`（SSE）

当前逻辑：

- LLM 返回 2–3 首**真实歌名**（含 artist、searchHint、platformTips），不提供下载链接
- 同时生成 `bgmStyle` 与 `rhythmNotes`
- 不生成占位节拍点；`beatPoints` 保持为空直到音频识别成功
- LLM 不可用时规则兜底推荐

兼容别名：`POST /projects/{projectId}/rhythm-plan/generate` 与 `/generate/stream` 行为与 `bgm-recommend` 相同。

## 4.3 选定 BGM 推荐项

`PUT /projects/{projectId}/rhythm-plan/bgm-selection`

请求体：

```json
{
  "recommendationId": "bgm_xxx"
}
```

- 写入 `selectedBgmId` 与 `selectedTrackName`
- 上传音频前必须先选定一首推荐曲目

## 4.4 保存节奏规划

`PUT /projects/{projectId}/rhythm-plan`

请求体：

```json
{
  "bgmStyle": "冷感氛围电子 + 轻鼓点",
  "selectedTrackName": "snow-dream-demo",
  "audioFileName": "demo-track.mp3",
  "analysisSource": "audio_upload",
  "analysisNotes": ["识别引擎：librosa 节拍跟踪"],
  "detectedBpm": 120,
  "audioDurationSec": 180.5,
  "rawBeatPoints": [0, 0.5, 1, 1.5, 2, 2.5],
  "coarseBeatPoints": [0, 1, 2],
  "beatMode": "beat_2",
  "beatPoints": [0, 0.5, 1, 1.5],
  "rhythmNotes": ["前 3 秒保证强开头"],
  "darkCutSuggestions": [15, 30, 45],
  "photoMotionSuggestions": ["照片素材优先慢推"],
  "recommendedBgm": [],
  "selectedBgmId": "bgm_xxx",
  "bgmPhase": "analyzed"
}
```

`analysisSource` 取值：

- `rule`：规则生成（历史兼容）
- `audio_upload`：音频识别成功
- `rule_fallback`：音频识别失败；**不写入占位节拍点**，需重新上传有效 BGM
- `manual`：用户手工编辑后保存

## 4.5 上传音频并识别节拍

`POST /projects/{projectId}/rhythm-plan/audio-upload`

- Content-Type: `multipart/form-data`
- 字段名：`audio`
- 支持 WAV / MP3 / M4A / AAC / OGG / MGG / FLAC / WMA
- 非 WAV 格式需服务端安装 `ffmpeg`
- **必须先** `bgm-selection` 选定推荐曲目
- 识别成功：`bgmPhase` → `analyzed`，写入节拍点
- 识别失败：返回 200，`analysisSource` 为 `rule_fallback`，`bgmPhase` 保持 `recommended`，节拍点清空

## 4.6 移除已绑定音频

`DELETE /projects/{projectId}/rhythm-plan/audio`

- 删除本地存储的音频文件
- 清空 `audioFileName` / `detectedBpm` / `audioDurationSec` / 节拍点
- 若已有 BGM 推荐则 `bgmPhase` 回退为 `recommended`

## 5. 分镜

## 5.1 获取分镜

`GET /projects/{projectId}/storyboard`

返回：

```json
{
  "segments": [],
  "validation": {
    "allSegmentsBoundToAsset": true,
    "locationContinuityPassed": true,
    "beatAlignmentPassed": true,
    "totalDurationSec": 60
  }
}
```

## 5.2 生成分镜

`POST /projects/{projectId}/storyboard:generate`

请求体：

```json
{
  "themeId": "theme_xxx",
  "targetDurationSec": 60,
  "beatMode": "beat_1",
  "selectedTrackName": "snow-dream-demo"
}
```

说明：

- 生成逻辑优先参考节拍点
- **前置条件**：节奏页 `bgmPhase === "analyzed"` 且 `analysisSource === "audio_upload"`，否则返回 400
- 分镜在当前实现中会覆盖该项目原有分镜
- 当前“生成分镜”是整表重建，不是增量追加

## 5.3 保存分镜

`PUT /projects/{projectId}/storyboard`

请求体：

```json
{
  "themeId": "theme_xxx",
  "segments": [
    {
      "id": "seg_xxx",
      "startTime": 0,
      "endTime": 1.5,
      "assetId": "KANAS_001",
      "shotDescription": "喀纳斯 - 蓝冰河流特写",
      "function": "opening_hook",
      "rhythm": "balanced",
      "beatMode": "beat_1",
      "beatPoints": [0, 0.5, 1, 1.5],
      "subtitle": "喀纳斯 / 蓝冰河流特写"
    }
  ]
}
```

说明：

- 当前接口用于整表覆盖保存
- 当需要批量调整时间线时可继续复用此接口

## 5.4 单条分镜编辑

`PUT /projects/{projectId}/storyboard/{segmentId}`

请求体：

```json
{
  "id": "seg_xxx",
  "startTime": 12,
  "endTime": 13,
  "assetId": "KANAS_010",
  "shotDescription": "喀纳斯 - 湖边回望镜头",
  "function": "transition",
  "rhythm": "balanced",
  "beatMode": "beat_1",
  "beatPoints": [12, 12.5, 13],
  "subtitle": "喀纳斯 / 湖边回望"
}
```

说明：

- 用于单条分镜详细编辑
- 前端保存成功后可直接返回分镜列表页

## 5.5 删除单条分镜

`DELETE /projects/{projectId}/storyboard/{segmentId}`

说明：

- 删除后返回最新分镜列表和校验结果

## 5.6 一期建议新增接口：后插一条分镜

`POST /projects/{projectId}/storyboard/insert`

请求体建议：

```json
{
  "afterSegmentId": "seg_xxx",
  "segment": {
    "assetId": "KANAS_010",
    "shotDescription": "喀纳斯 - 湖边回望镜头",
    "function": "transition",
    "rhythm": "balanced",
    "beatMode": "beat_1",
    "beatPoints": [12, 12.5, 13],
    "subtitle": "喀纳斯 / 湖边回望",
    "startTime": 12,
    "endTime": 13
  }
}
```

说明：

- 最小改动版只支持“在当前镜头后插一条”
- 插入后需要重排后续镜头的开始和结束时间

## 5.7 一期建议新增接口：顺序调整

`PUT /projects/{projectId}/storyboard/reorder`

请求体建议：

```json
{
  "orderedSegmentIds": ["seg_a", "seg_c", "seg_b", "seg_d"]
}
```

说明：

- 对应前端“上移 / 下移”
- 后端按新顺序保留每条分镜原时长，并重算整条时间线
- 一期暂不要求支持自由拖拽排序

## 6. 导出信息

## 6.1 获取导出信息

`GET /projects/{projectId}/export-plan`

## 6.2 保存导出信息

`PUT /projects/{projectId}/export-plan`

请求体：

```json
{
  "title": "原来冬天的阿勒泰，真的像童话",
  "shortTitle": "阿勒泰雪国童话",
  "description": "把雪、木屋和路上的人，剪成一段安静但有记忆点的冬日旅程。",
  "tags": ["阿勒泰", "旅行剪辑", "冬日雪景"],
  "coverSuggestion": "优先使用禾木木屋群远景，标题放在右下角保留雪景留白。"
}
```

## 7. 导出预览

## 7.1 生成 Markdown 预览

`POST /projects/{projectId}/exports/markdown`

## 7.2 生成 JSON 预览

`POST /projects/{projectId}/exports/json`

## 7.3 生成 YAML 预览

`POST /projects/{projectId}/exports/yaml`

## 7.4 生成 CSV 预览

`POST /projects/{projectId}/exports/csv`

返回分镜时间线 CSV（`segmentId,startTime,endTime,assetId,function,rhythm,beatMode,subtitle`）。

返回结构：

```json
{
  "projectId": "proj_xxx",
  "format": "markdown",
  "fileName": "proj_xxx-timeline.md",
  "content": "# 导出脚本 ..."
}
```

导出内容包含：

- 项目信息
- 当前主题
- 节奏规划
- 分镜时间线
- 分镜校验摘要（`storyboardValidation`）
- 导出文案校验（`exportValidation`）
- 标题
- 标签
- 文案

## 8. 关键业务说明

- workflow 顺序已调整为：新建 → 录入 → 主题 → 节奏 → 分镜 → 导出
- 分镜生成依赖节奏规划中的节拍点
- 导出阶段当前由人工填写标题、标签和文案
- 后续如接入 LLM，只需复用 `export-plan` 结构即可
## 9. 二期 LLM Provider API

已实现 provider 配置与 OAuth 授权。Registry 中 **OpenAI** 已合并原 `openai-compatible`（`openai-compatible` 仍可作为 providerId 别名解析）。

- `api_key`（已接入）
- `oauth`（OpenAI、Google；Authorization Code + PKCE）
- `device_code`（OpenAI 预留，尚未接入）

**权限**：`/llm/*` 配置与管理接口仅 **导演（director）** 可访问，需携带 Session Token（`Authorization: Bearer` 或 `X-Session-Token`）。剪辑账号可正常使用主题/分镜/导出等 LLM 业务接口，共用系统级 Provider 配置。

LLM 业务接口（主题 / 分镜 / 导出 / 节奏文案）在 `ApiResponse.meta` 中返回：

- `llmStatus`：`success` | `fallback_rule` | `not_configured` | `timeout` | `empty_response` | `parse_error` | ...
- `llmMessage`：用户可读说明
- `llmProviderId` / `llmUsedFallback`

兜底口径详见 `regression-sprint5.md` §5。

### 9.0 流式 LLM 接口（SSE）

长耗时 LLM 任务优先使用 `text/event-stream`，事件类型：

- `progress`：`stage` / `message` / `progress` / `detail`
- `complete`：`data` + `meta`（与非流式接口一致）
- `error`：错误消息

| 业务 | 路径 |
|------|------|
| 主题 LLM | `POST /projects/{id}/themes/generate-llm/stream` |
| 分镜 LLM | `POST /projects/{id}/storyboard/generate-llm/stream` |
| 节奏 BGM 推荐 | `POST /projects/{id}/rhythm-plan/bgm-recommend/stream` |
| 音频识别 | `POST /projects/{id}/rhythm-plan/audio-upload/stream` |
| 导出建议 | `POST /projects/{id}/export-plan/suggest/stream` |

前端通过 `Accept: text/event-stream` 调用，浏览器直连 FastAPI（见 `frontend/lib/api-base.ts`）。

### 9.1 获取 provider 列表

`GET /llm/providers`

返回字段建议：

- `providerId`
- `providerName`
- `authTypes`
- `defaultBaseUrl`
- `status`

### 9.2 保存 provider 配置

`POST /llm/providers/{providerId}/config`

请求体建议：

```json
{
  "authType": "api_key",
  "baseUrl": "https://api.example.com/v1",
  "model": "example-model",
  "apiKey": "server-side-only"
}
```

### 9.3 发起 OAuth 授权

`POST /llm/providers/{providerId}/oauth/start`

返回：

- `authorizationUrl`
- `state`
- `message`

### 9.4 OAuth 回调

`POST /llm/providers/{providerId}/oauth/callback`

请求体：

```json
{
  "code": "authorization_code",
  "state": "csrf_state_from_start"
}
```

前端回调页 `/settings/llm/oauth/callback` 读取 query 后调用此接口完成 token 交换。

### 9.5 断开 OAuth

`POST /llm/providers/{providerId}/oauth/revoke`

### 9.6 Device Code（预留）

`POST /llm/providers/{providerId}/device-code/start`

返回字段建议：

- `deviceCode`
- `userCode`
- `verificationUri`
- `expiresIn`
- `interval`

### 9.7 查询授权状态

`GET /llm/providers/{providerId}/status`

返回字段建议：

- `authType`
- `status`
- `expiresAt`
- `model`
- `baseUrl`
