# video-sop-editor

低重构成本版的一期工程骨架：

- `frontend/`: Next.js 前端，负责页面、交互、表单、工作台展示。
- `backend/`: FastAPI 后端，负责领域模型、生成接口、导出接口和后续可扩展的视频处理入口。
- `docs/`: 产品与研发参考文档。

## 技术栈

前端：

- Next.js App Router
- React
- TypeScript
- Tailwind CSS

后端：

- FastAPI
- Pydantic
- SQLModel
- SQLite
- Uvicorn

当前实现目标：

- 跑通项目总览、素材、主题、分镜、节奏、发布方案工作台
- 提供可联调的示例 API
- 为二期拆分视频分析、节拍识别、粗剪服务保留边界

## 目录结构

```text
frontend/
  app/
  components/
  lib/
  types/
backend/
  app/
    api/routes/
    core/
    services/
    models/
docs/
```

## 需要安装的依赖

前端依赖：

```powershell
cd frontend
npm install
```

后端依赖：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

音频节拍识别额外要求：

- 系统 PATH 中可调用 `ffmpeg`（用于 MP3 / FLAC 等格式转 WAV）
- `requirements.txt` 已包含 `librosa`；若安装失败，系统仍会回退到基础能量检测

## 本地调试步骤

1. 启动后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python init_db.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

2. 新开一个终端启动前端

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

3. 打开浏览器访问

```text
http://127.0.0.1:3000
```

## 环境变量

前端 `.env.local`：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

后端 `.env` 可选：

```env
APP_ENV=development
APP_NAME=video-sop-editor-api
APP_HOST=127.0.0.1
APP_PORT=8000
DATABASE_URL=sqlite:///./video_sop.db
```

## 开发建议

- 一期先把领域结构、数据模型、接口边界做稳。
- 当前后端已切到 `SQLite + SQLModel`，启动时会自动建表并注入示例数据。
- 二期新增视频分析、节拍识别、FFmpeg/MoviePy 粗剪时，优先放到 `backend/app/services/` 下的独立模块。
- 音频节拍识别依赖 `ffmpeg`（转码）和 `librosa`（主识别引擎）；未安装 librosa 时会自动回退到能量起音检测。
- 前端尽量只消费接口，不把业务生成逻辑写死在页面组件里。
- 修改中文源码、文档或 PowerShell 脚本前，先看 `docs/encoding-guardrails.md`，避免 UTF-8 / GBK 误读导致乱码回流。
- 建议首次 clone 后执行 `powershell -ExecutionPolicy Bypass -File scripts\install-git-hooks.ps1`，提交前自动扫描乱码。

## SQLite / SQLModel 说明

- 默认数据库文件位置：`backend/video_sop.db`
- 首次初始化命令：

```powershell
cd backend
.venv\Scripts\activate
python init_db.py
```

- 如果你想重置本地演示数据：

```powershell
cd backend
del video_sop.db
python init_db.py
```
