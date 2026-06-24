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

## 4.1 获取节奏规划

`GET /projects/{projectId}/rhythm-plan`

## 4.2 生成节奏规划

`POST /projects/{projectId}/rhythm-plan:generate`

当前逻辑：

- 根据项目目标时长生成 beat points
- 根据视频类型推荐 beat mode
- 根据素材和主题生成节奏说明

## 4.3 保存节奏规划

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
  "beatMode": "beat_2",
  "beatPoints": [0, 0.5, 1, 1.5],
  "rhythmNotes": ["前 3 秒保证强开头"],
  "darkCutSuggestions": [15, 30, 45],
  "photoMotionSuggestions": ["照片素材优先慢推"]
}
```

`analysisSource` 取值：

- `rule`：规则生成
- `audio_upload`：音频识别成功
- `rule_fallback`：音频识别失败，已回退规则生成
- `manual`：用户手工编辑后保存

## 4.4 上传音频并识别节拍

`POST /projects/{projectId}/rhythm-plan/audio-upload`

- Content-Type: `multipart/form-data`
- 字段名：`audio`
- 支持 WAV / MP3 / M4A / AAC / OGG / MGG / FLAC / WMA
- 非 WAV 格式需服务端安装 `ffmpeg`
- 识别失败时不返回 400，而是写入 `rule_fallback` 节奏规划

## 4.5 移除已绑定音频

`DELETE /projects/{projectId}/rhythm-plan/audio`

- 删除本地存储的音频文件
- 清空 `audioFileName` / `detectedBpm` / `audioDurationSec` / `rawBeatPoints`
- 保留当前 beat points 与节奏说明，供继续手工编辑

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
- 标题
- 标签
- 文案

## 8. 关键业务说明

- workflow 顺序已调整为：新建 → 录入 → 主题 → 节奏 → 分镜 → 导出
- 分镜生成依赖节奏规划中的节拍点
- 导出阶段当前由人工填写标题、标签和文案
- 后续如接入 LLM，只需复用 `export-plan` 结构即可
## 9. 二期 LLM Provider API 预留

二期建议新增 provider 配置与授权接口，统一支持三种认证模式：

- `api_key`
- `oauth`
- `device_code`

建议接口：

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

返回字段建议：

- `authorizationUrl`
- `state`
- `codeChallenge`

### 9.4 OAuth 回调

`GET /llm/providers/{providerId}/oauth/callback`

用途：

- 接收授权码
- 服务端换取 access token / refresh token
- 持久化授权状态

### 9.5 发起 Device Code 授权

`POST /llm/providers/{providerId}/device-code/start`

返回字段建议：

- `deviceCode`
- `userCode`
- `verificationUri`
- `expiresIn`
- `interval`

### 9.6 查询授权状态

`GET /llm/providers/{providerId}/status`

返回字段建议：

- `authType`
- `status`
- `expiresAt`
- `model`
- `baseUrl`
