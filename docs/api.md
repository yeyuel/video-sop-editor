# 旅行短视频剪辑导演助手 API 设计 v1

## 1. 文档目标

本文档定义一期 MVP 的接口设计，供前后端协作、联调和后续自动剪辑模块扩展使用。

设计原则：

- 以 REST 风格为主。
- 以项目为聚合根组织资源。
- 所有生成型接口都必须继承“不可臆造素材”的约束。
- 所有结构化输出都支持后续导出为 JSON 或 YAML。

## 2. 通用规范

## 2.1 Base URL

示例：

```text
/api/v1
```

## 2.2 Content-Type

```text
application/json
```

## 2.3 统一响应格式

成功响应：

```json
{
  "success": true,
  "data": {},
  "meta": {
    "requestId": "req_123"
  }
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "platform is required",
    "details": []
  },
  "meta": {
    "requestId": "req_123"
  }
}
```

## 2.4 错误码建议

| 错误码 | 说明 |
| --- | --- |
| `INVALID_ARGUMENT` | 请求参数错误 |
| `NOT_FOUND` | 资源不存在 |
| `CONFLICT` | 资源冲突 |
| `VALIDATION_FAILED` | 业务校验失败 |
| `GENERATION_FAILED` | 内容生成失败 |
| `EXPORT_FAILED` | 导出失败 |

## 3. 枚举定义

## 3.1 Platform

```json
["wechat_channel", "douyin", "xiaohongshu", "bilibili"]
```

## 3.2 VideoType

```json
["travel_montage", "emotion_film", "guide_video", "city_short", "vlog"]
```

## 3.3 MediaType

```json
["video", "photo", "drone_video", "mobile_video", "camera_video"]
```

## 3.4 ShotType

```json
["wide", "medium", "close_up", "human", "animal", "transition"]
```

补充说明：

- `medium` 对应 `中景`，表示同时包含景别信息和人物或主体关系的镜头类型。

## 3.5 InformationDensity

```json
["low", "medium", "high"]
```

## 3.6 BeatMode

```json
["none", "beat_1", "beat_2", "strong_weak", "custom_template"]
```

## 4. 核心数据结构

## 4.1 Project

```json
{
  "id": "proj_001",
  "name": "阿勒泰雪国片",
  "destination": "阿勒泰",
  "platform": "xiaohongshu",
  "targetDurationSec": 60,
  "videoType": "emotion_film",
  "stylePreference": "冷感、童话、慢高潮",
  "routeText": "将军山-喀纳斯-禾木",
  "status": "draft",
  "createdAt": "2026-06-16T10:00:00Z",
  "updatedAt": "2026-06-16T10:00:00Z"
}
```

## 4.2 Asset

```json
{
  "assetId": "KANAS_008",
  "projectId": "proj_001",
  "location": "喀纳斯",
  "scene": "蓝冰水流动",
  "mediaType": "drone_video",
  "shotType": "medium",
  "emotionTags": ["冷", "静"],
  "visualTags": ["冷蓝", "白雪"],
  "informationDensity": "medium",
  "suggestedDurationSec": 1.5,
  "functionTags": ["slow_climax"]
}
```

## 4.3 NarrativeTheme

```json
{
  "id": "theme_001",
  "projectId": "proj_001",
  "title": "雪国童话感",
  "summary": "以冷色、静谧和童话感构成一路进入阿勒泰冬天的沉浸体验",
  "coreEmotion": "安静、遥远、童话",
  "rhythmProfile": "开头钩子快，主体慢推进，3/4 位置主高潮",
  "platformReason": "适合小红书偏氛围与审美表达的内容风格"
}
```

## 4.4 StoryboardSegment

```json
{
  "id": "seg_001",
  "projectId": "proj_001",
  "themeId": "theme_001",
  "startTime": 0.0,
  "endTime": 0.6,
  "assetId": "HEMU_012",
  "shotDescription": "禾木蓝调木屋群远景",
  "function": "opening_hook",
  "rhythm": "slow_impact",
  "beatMode": "beat_1",
  "beatPoints": [0.0, 0.6],
  "subtitle": "元旦落地阿勒泰"
}
```

## 4.5 RhythmPlan

```json
{
  "bgmStyle": "冷感氛围电子 + 轻钢琴铺底",
  "selectedTrackName": "snow-dream-demo",
  "beatMode": "strong_weak",
  "beatPoints": [0.0, 0.5, 1.0, 1.5],
  "rhythmNotes": [
    "前 3 秒保留强钩子",
    "中段降低切换频率，突出雪国静感"
  ],
  "darkCutSuggestions": [12.5, 28.0],
  "photoMotionSuggestions": ["对静态雪景做缓慢推进"]
}
```

## 5. 项目接口

## 5.1 创建项目

`POST /api/v1/projects`

请求体：

```json
{
  "name": "阿勒泰雪国片",
  "destination": "阿勒泰",
  "platform": "xiaohongshu",
  "targetDurationSec": 60,
  "videoType": "emotion_film",
  "stylePreference": "冷感、童话、慢高潮",
  "routeText": "将军山-喀纳斯-禾木"
}
```

响应体：

```json
{
  "success": true,
  "data": {
    "id": "proj_001"
  },
  "meta": {
    "requestId": "req_001"
  }
}
```

## 5.2 查询项目列表

`GET /api/v1/projects`

查询参数：

- `keyword`
- `platform`
- `status`
- `page`
- `pageSize`

## 5.3 查询项目详情

`GET /api/v1/projects/{projectId}`

## 5.4 更新项目

`PATCH /api/v1/projects/{projectId}`

## 6. 素材接口

## 6.1 批量创建素材卡片

`POST /api/v1/projects/{projectId}/assets:batchCreate`

请求体：

```json
{
  "assets": [
    {
      "assetId": "KANAS_008",
      "location": "喀纳斯",
      "scene": "蓝冰水流动",
      "mediaType": "drone_video",
      "shotType": "medium",
      "emotionTags": ["冷", "静"],
      "visualTags": ["冷蓝", "白雪"],
      "informationDensity": "medium",
      "suggestedDurationSec": 1.5,
      "functionTags": ["symbolic_visual"]
    }
  ]
}
```

校验规则：

- `assetId` 必填且项目内唯一。
- `location` 必填。
- `scene` 必填。
- `shotType` 必须支持 `medium`，用于标记中景镜头。

## 6.2 导入素材脑图文本

`POST /api/v1/projects/{projectId}/mindmap:parse`

请求体：

```json
{
  "rawText": "阿勒泰\n- 将军山：落日、滑雪、缆车\n- 喀纳斯：蓝冰水、赤狐、晨雾\n- 禾木：木屋、炊烟、河流"
}
```

响应体：

```json
{
  "success": true,
  "data": {
    "groups": [
      {
        "name": "阿勒泰",
        "children": [
          {
            "name": "将军山",
            "children": ["落日", "滑雪", "缆车"]
          }
        ]
      }
    ]
  },
  "meta": {
    "requestId": "req_002"
  }
}
```

## 6.3 查询素材列表

`GET /api/v1/projects/{projectId}/assets`

支持过滤：

- `location`
- `scene`
- `mediaType`
- `shotType`

## 7. 主题生成接口

## 7.1 生成主题方向

`POST /api/v1/projects/{projectId}/themes:generate`

请求体：

```json
{
  "count": 3
}
```

业务规则：

- 主题生成必须基于项目素材表。
- 主题数量默认 3，最大 5。

响应体：

```json
{
  "success": true,
  "data": {
    "themes": [
      {
        "id": "theme_001",
        "title": "雪国童话感",
        "summary": "以冷色与安静构建沉浸式冬日体验",
        "coreEmotion": "童话",
        "rhythmProfile": "前快后慢再抬升",
        "platformReason": "适合小红书氛围表达"
      }
    ]
  },
  "meta": {
    "requestId": "req_003"
  }
}
```

## 7.2 选择主题

`POST /api/v1/projects/{projectId}/theme-selection`

请求体：

```json
{
  "themeId": "theme_001"
}
```

## 8. 分镜接口

## 8.1 生成分镜

`POST /api/v1/projects/{projectId}/storyboard:generate`

请求体：

```json
{
  "themeId": "theme_001",
  "targetDurationSec": 60,
  "beatMode": "beat_1",
  "selectedTrackName": "snow-dream-demo"
}
```

生成约束：

- 不得创造素材表中不存在的镜头。
- 每个镜头必须引用 `assetId`。
- 必须校验 `location` 连续性。
- 必须标记镜头功能位。
- 已提供具体 BGM 或节拍模板时，镜头起止时间应优先贴合节拍点。

响应体：

```json
{
  "success": true,
  "data": {
    "segments": [
      {
        "id": "seg_001",
        "startTime": 0.0,
        "endTime": 0.6,
        "assetId": "HEMU_012",
        "shotDescription": "禾木蓝调木屋群远景",
        "function": "opening_hook",
        "rhythm": "slow_impact",
        "beatMode": "beat_1",
        "beatPoints": [0.0, 0.6],
        "subtitle": "元旦落地阿勒泰"
      }
    ],
    "validation": {
      "allSegmentsBoundToAsset": true,
      "locationContinuityPassed": true,
      "beatAlignmentPassed": true,
      "totalDurationSec": 59.8
    }
  },
  "meta": {
    "requestId": "req_004"
  }
}
```

## 8.2 手动更新分镜

`PATCH /api/v1/projects/{projectId}/storyboard`

请求体：

```json
{
  "segments": [
    {
      "id": "seg_001",
      "assetId": "KANAS_003",
      "startTime": 0.0,
      "endTime": 0.5,
      "beatMode": "beat_2",
      "beatPoints": [0.0, 0.5],
      "subtitle": "第一眼就像进入雪国"
    }
  ]
}
```

## 8.3 查询分镜

`GET /api/v1/projects/{projectId}/storyboard`

## 9. 节奏与发布接口

## 9.1 生成音乐节奏方案

`POST /api/v1/projects/{projectId}/rhythm-plan:generate`

请求体：

```json
{
  "themeId": "theme_001",
  "selectedTrackName": "snow-dream-demo"
}
```

响应体示例：

```json
{
  "success": true,
  "data": {
    "bgmStyle": "冷感氛围电子 + 轻钢琴铺底",
    "selectedTrackName": "snow-dream-demo",
    "beatMode": "strong_weak",
    "beatPoints": [0.0, 0.5, 1.0, 1.5],
    "rhythmNotes": [
      "前 3 秒保留强钩子",
      "中段降低切换频率，突出雪国静感",
      "3/4 位置加入航拍主高潮"
    ],
    "darkCutSuggestions": [12.5, 28.0],
    "photoMotionSuggestions": ["对静态雪景做缓慢推进"]
  },
  "meta": {
    "requestId": "req_005"
  }
}
```

业务规则：

- 已有具体 BGM 时，系统应优先返回可用于卡点的 `beatMode` 和 `beatPoints`。
- 尚未选定具体 BGM 时，可返回 `custom_template` 类型的节拍模板。

## 9.2 生成发布方案

`POST /api/v1/projects/{projectId}/publish-plan:generate`

请求体：

```json
{
  "themeId": "theme_001"
}
```

响应体示例：

```json
{
  "success": true,
  "data": {
    "title": "原来冬天的阿勒泰，真的像童话",
    "shortTitle": "阿勒泰雪国童话",
    "description": "把元旦在阿勒泰看到的雪、河流和木屋，剪成了一场安静的冬日旅行。",
    "tags": ["阿勒泰", "旅行剪辑", "冬日童话"],
    "coverSuggestion": "选择禾木蓝调木屋群远景，叠加短标题"
  },
  "meta": {
    "requestId": "req_006"
  }
}
```

## 10. 导出接口

## 10.1 导出 Markdown

`POST /api/v1/projects/{projectId}/exports/markdown`

## 10.2 导出 JSON

`POST /api/v1/projects/{projectId}/exports/json`

## 10.3 导出 YAML

`POST /api/v1/projects/{projectId}/exports/yaml`

## 10.4 导出 PDF

`POST /api/v1/projects/{projectId}/exports/pdf`

统一响应：

```json
{
  "success": true,
  "data": {
    "fileName": "altay-storyboard.yaml",
    "downloadUrl": "/downloads/altay-storyboard.yaml",
    "format": "yaml"
  },
  "meta": {
    "requestId": "req_007"
  }
}
```

## 11. 分镜 JSON Schema 建议

```json
{
  "projectId": "proj_001",
  "themeId": "theme_001",
  "targetDurationSec": 60,
  "segments": [
    {
      "id": "seg_001",
      "startTime": 0.0,
      "endTime": 0.6,
      "assetId": "HEMU_012",
      "location": "禾木",
      "shotDescription": "禾木蓝调木屋群远景",
      "function": "opening_hook",
      "rhythm": "slow_impact",
      "beatMode": "beat_1",
      "beatPoints": [0.0, 0.6],
      "subtitle": "元旦落地阿勒泰"
    }
  ],
  "rhythmPlan": {
    "bgmStyle": "冷感氛围电子",
    "selectedTrackName": "snow-dream-demo",
    "beatMode": "strong_weak",
    "beatPoints": [0.0, 0.5, 1.0, 1.5],
    "darkCutSuggestions": [12.5, 28.0]
  },
  "publishPlan": {
    "title": "原来冬天的阿勒泰，真的像童话",
    "shortTitle": "阿勒泰雪国童话",
    "tags": ["阿勒泰", "旅行剪辑"]
  }
}
```

## 12. 分镜 YAML 示例

```yaml
projectId: proj_001
themeId: theme_001
targetDurationSec: 60
segments:
  - id: seg_001
    startTime: 0.0
    endTime: 0.6
    assetId: HEMU_012
    location: 禾木
    shotDescription: 禾木蓝调木屋群远景
    function: opening_hook
    rhythm: slow_impact
    beatMode: beat_1
    beatPoints: [0.0, 0.6]
    subtitle: 元旦落地阿勒泰
rhythmPlan:
  bgmStyle: 冷感氛围电子
  selectedTrackName: snow-dream-demo
  beatMode: strong_weak
  beatPoints: [0.0, 0.5, 1.0, 1.5]
publishPlan:
  title: 原来冬天的阿勒泰，真的像童话
  shortTitle: 阿勒泰雪国童话
  tags: [阿勒泰, 旅行剪辑]
```

## 13. LLM Prompt 约束建议

所有生成接口建议统一注入以下系统约束：

- 你是旅行短视频导演，请基于素材表生成 45 至 60 秒分镜。
- 必须遵守真实路线，不得混淆地点归属。
- 不得创造素材表中不存在的镜头。
- 每个分镜必须引用 `assetId`。
- 按镜头信息量分配时长。
- 按开头、1/4、1/2、3/4、结尾设计功能位。
- 输出 BGM 风格和节奏建议，而不是只给歌名。
- 如果已提供具体 BGM 或节拍模板，镜头时长要优先贴合 `beatPoints`。

## 14. 二期兼容性要求

为了支持自动粗剪，本期接口需提前保证：

- 分镜 JSON 字段稳定。
- 同步提供等价的 YAML 导出能力。
- 时间字段使用秒级数值。
- 每个镜头包含 `assetId`。
- 每个镜头可选包含 `beatMode` 与 `beatPoints`。
- 字幕、节奏、BGM 建议可被二期处理器消费。
