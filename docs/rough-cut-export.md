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
4. 重启剪映或刷新草稿列表后打开

### 2.3 BGM 音频轨

| 条件 | 行为 |
|------|------|
| `rhythmPlan.audioFilePath` 指向有效文件 | 添加 BGM 轨，覆盖整段时间线 |
| 未上传 / 文件不存在 | 跳过音频轨，仅导出视频 + 字幕 |

## 3. 字段映射

### 3.1 分镜 → 剪映草稿

| 分镜字段 | 剪映字段 | 说明 |
|---------|---------|------|
| `startTime` / `endTime` | `segments[].target_timerange` | 秒 → 微秒 |
| `asset.relativePath` + `project.mediaRoot` | `materials.videos[].path` | 素材绝对路径 |
| `subtitle` | `materials.texts[]` + 文本轨 | UTF-16 字节 range |
| BGM 上传文件 | `materials.audios[]` + audio 轨 | 可选 |

### 3.2 版本说明

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
