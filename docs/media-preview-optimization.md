# 大视频预览加载优化调研

## 现状与瓶颈

录入页媒体库预览链路：

```
浏览器 <video> → Next.js 同源代理 → FastAPI FileResponse → 磁盘原始文件
```

主要慢点：

| 因素 | 影响 |
|------|------|
| **整文件直传** | 4K/HEVC 原片动辄数百 MB～数 GB，首帧与 seek 需拉大量数据 |
| **编码格式** | DJI 等设备常见 H.265，浏览器解码与缓冲成本高 |
| **无预览轨** | 没有低码率代理文件，无法「先看小文件再决定是否看原片」 |
| **Range 未透传（已修复）** | 视频拖动依赖 HTTP Range；代理未转发会导致重复全量下载 |
| **无占位图** | 转码/加载期间黑屏，体感慢 |

## 方案对比

### 1. 服务端转码低码率预览（已实现，推荐 P0）

**做法**：首次请求 `quality=fast` 时用 ffmpeg 生成 720p H.264 + `faststart`，缓存到 `storage/media-preview-cache/{projectId}/`。

**优点**：
- 文件体积通常降为原片 5%～15%
- H.264 浏览器兼容好
- `faststart` 把 moov 移到文件头，首帧更快
- 缓存命中后几乎即时播放

**代价**：
- 首次选中大文件需等待转码（ultrafast preset 仍可能数十秒）
- 无音频（预览录入场景可接受）
- 画质下降（可配置 `MEDIA_PREVIEW_MAX_WIDTH` / `MEDIA_PREVIEW_CRF`）

**环境变量**：

```env
MEDIA_PREVIEW_MAX_WIDTH=1280
MEDIA_PREVIEW_CRF=28
MEDIA_PREVIEW_PRESET=ultrafast
```

### 2. 封面 Poster（已实现，P0）

**做法**：`GET .../media-library/poster` 用 ffmpeg 抽 0.5s 帧为 JPEG，同样按源文件指纹缓存。

**优点**：选中文件后立即有画面，掩盖转码等待。

### 3. HTTP Range 支持（已修复，P1）

Next 代理转发 `Range` / `Content-Range` / `Accept-Ranges`，Starlette `FileResponse` 原生支持 206 分片。

### 4. 前端 `preload="metadata"`（已实现）

只预加载元数据，减少无效字节；配合 poster 改善首屏。

### 5. 未实现、可后续考虑

| 方案 | 说明 | 复杂度 |
|------|------|--------|
| **HLS/DASH 分片** | 自适应码率，seek 最优 | 高 |
| **后台预热** | 扫描目录后异步转码 Top N | 中 |
| **WebCodecs 客户端解码** | 仍须传原片，收益有限 | 中 |
| **缩略图精灵图** | 时间轴 scrub 预览 | 中 |
| **图片 WebP 压缩预览** | 大图预览加速 | 低 |

## API

```
GET /projects/{id}/assets/media-library/preview?relativePath=...&quality=fast|original
GET /projects/{id}/assets/media-library/poster?relativePath=...
```

- 视频默认 `quality=fast`
- 图片/音频仍直传原文件
- 转码失败返回 503，前端可切换「原画质」

## 验证建议

1. 选中 >500MB 4K 样片：应先出现 poster，再显示「正在生成低码率预览」
2. 同一文件第二次打开：缓存命中，应明显快于首次
3. 浏览器 Network：确认存在 `Range` 请求与 `206 Partial Content`
4. 切换「原画质」：应走原始大文件（适合核对细节时）

## 依赖

服务端需安装 **ffmpeg**（与 Vision 抽帧共用）。未安装时 fast/poster 返回 503。

## 连接池注意

预览/封面接口会在 ffmpeg 转码与文件流传输阶段占用较长时间。实现上已在读取 `mediaRoot` 后立即释放数据库连接，避免与 Range 分片请求叠加导致连接池耗尽。
