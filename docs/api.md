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
  "beatMode": "beat_1",
  "beatPoints": [0, 0.5, 1, 1.5],
  "rhythmNotes": ["前 3 秒保证强开头"],
  "darkCutSuggestions": [15, 30, 45],
  "photoMotionSuggestions": ["照片素材优先慢推"]
}
```

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
