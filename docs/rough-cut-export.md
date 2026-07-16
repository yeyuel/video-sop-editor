# 粗剪结构导出（Sprint 17）

## 1. 目标

从现有分镜时间线导出可在剪辑软件中打开的粗剪结构，**不渲染成片**。

当前已实现（按优先级）：

1. **剪映草稿一键写入**（推荐）
2. **剪映草稿 JSON 下载**（手动备份 / 调试）
3. **CMX3600 EDL**（Premiere / DaVinci 等 NLE）

## 2. 一键写入剪映（推荐）

### 2.1 配置项

| 字段 | 存储位置 | 说明 |
|------|---------|------|
| `jianyingDraftRoot` | 项目配置 | 剪映草稿根目录，导出页可编辑并持久化 |
| 系统默认 | 后端解析 | `%LOCALAPPDATA%\JianyingPro\User Data\Projects\com.lveditor.draft` |

### 2.2 写入行为

`POST /api/v1/projects/{projectId}/exports/capcut/deploy`

1. 在 `jianyingDraftRoot` 下新建 `{projectId}-{导出标题}` 文件夹
2. 写入 **`draft_content.json`** 与 **`draft_meta_info.json`**（内容相同）
3. 若节奏页已上传 BGM 且文件仍存在，自动添加 **audio 轨**；无 BGM 不阻断流程
4. 根据分镜策略写入基础叠化、照片缩放关键帧和重点字幕样式
5. 重启剪映或刷新草稿列表后打开

### 2.3 BGM 音频轨

| 条件 | 行为 |
|------|------|
| `rhythmPlan.audioFilePath` 指向有效文件 | 添加 BGM 轨，覆盖整段时间线，默认 0.4s 淡入、1s 淡出 |
| 未上传 / 文件不存在 | 跳过音频轨，仅导出视频 + 字幕 |

## 3. 字段映射

### 3.1 分镜 → 剪映草稿

| 分镜字段 | 剪映字段 | 说明 |
|---------|---------|------|
| `startTime` / `endTime` | `segments[].target_timerange` | 秒 → 微秒 |
| `asset.relativePath` + `project.mediaRoot` | `materials.videos[].path` | 素材绝对路径 |
| `subtitle` | `materials.texts[]` + 文本轨 | UTF-16 字节 range；默认 **悠然体**、字号 15 的 40%（6.0），长文本自动缩小 |
| 压缩口播块（`jianying_native_tts`） | “最终字幕（剪映朗读源）”文本轨 | 替代逐镜头原字幕，同一份文本同时用于画面显示和剪映朗读 |
| Edge TTS 口播音频 | 独立“口播”音轨 + “最终字幕（口播同步）”文本轨 | 支持智能匹配或指定中文音色；字幕按真实发音边界对齐，重新生成后立即替换旧音频 |
| `transitionPolicy=fade_or_match_cut` | `materials.transitions[]` | 写入剪映内置“叠化”，时长按相邻镜头长度限制在 0.2-0.5s |
| `motionPolicy=slow_push/gentle_zoom` | `segments[].common_keyframes` | 仅对照片写入等比缩放关键帧；视频素材保持原始运动 |
| `attentionRole/function` | 字幕文字样式 | 钩子、反转、高潮、收尾字幕适度放大并加粗 |
| `subtitlePolicy` | 字幕字号、粗体与透明度 | 支持 `standard`、`emphasis`、`info`、`minimal`；留空时按叙事角色自动推断 |
| BGM 上传文件 | `materials.audios[]` + audio 轨 | 可选；默认 **0.4s 淡入 + 1s 淡出**（`materials.audio_fades`，剪映内可再调） |

### 3.2 字幕与 BGM 默认样式

| 项 | 默认 | 剪映内可调 |
|----|------|-----------|
| 字幕字体 | 悠然体（内置 resource_id `349311`） | 是 |
| 字幕字号 | 默认 6.0；重点字幕最高 6.6；超过 18/24/32 字分级缩小，最低 4.2 | 是 |
| BGM 开始/结束 | 0.4s 淡入、1s 淡出（`materials.audio_fades`） | 是 |
| 缓冲转场 | 叠化；硬切和干净切不添加转场材料 | 是 |
| 照片动效 | 慢推 1.00→1.12，轻缩放 1.02→1.08 | 是 |

字体 ID 参考 pyJianYingDraft `FontType.悠然体`；若剪映版本未内置该字体，会回退为默认字体，可在剪映中批量替换。

### 3.3 版本说明

| 版本 | 状态 |
|------|------|
| 剪映 5.9.x | 推荐（明文 JSON） |
| 剪映 6.0+ | 可能加密，不保证识别 |

## 4. API

```
GET  /api/v1/projects/{projectId}/exports/capcut-defaults   # 默认/有效草稿根目录
POST /api/v1/projects/{projectId}/exports/capcut/deploy     # 一键写入（优先）
POST /api/v1/projects/{projectId}/exports/capcut            # 下载 bundle JSON
POST /api/v1/projects/{projectId}/exports/edl               # EDL
```

下载 bundle 的 `sections` 含两个独立 JSON：

- `sections.draft_content.json`
- `sections.draft_meta_info.json`

## 5. 手工验证

1. 导出页确认「剪映草稿根目录」路径正确
2. 点击 **写入剪映草稿目录**
3. 重启剪映，在草稿列表打开新项目
4. 确认视频轨、字幕轨；若已上传 BGM，确认 audio 轨存在

## 6. 测试

```powershell
cd backend
python -m pytest tests/test_export_capcut.py tests/test_regression_sprint17_export.py -q
```
