# video-sop-editor

旅行短视频 SOP 工作台：**新建 → 录入 → 主题 → 节奏（BGM）→ 分镜 → 导出**。

- `frontend/` — Next.js 前端（页面、交互、工作流）
- `backend/` — FastAPI 后端（领域模型、LLM、音频分析、导出）
- `docs/` — 产品与技术文档

**二期（Sprint 1～10）**：已关闭。**三期 Sprint 11 起**见 [`docs/phase3-master.md`](docs/phase3-master.md) / [`docs/phase3-checklist.md`](docs/phase3-checklist.md)。

## 技术栈

| 层 | 栈 |
|----|-----|
| 前端 | Next.js App Router、React、TypeScript、Tailwind CSS |
| 后端 | FastAPI、Pydantic、SQLModel、SQLite、Uvicorn |
| 音频 | ffmpeg（转码）、librosa（节拍识别，可选） |
| LLM | Provider Registry + API Key（OAuth 预留三期） |

## 本地开发

### 1. 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python init_db.py
python run_dev.py
# 等价于：uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

停止服务时若仍有视频预览转码或 SSE 流式任务，进程会在数秒内自动中断 ffmpeg 并退出；超时后请再按一次 `Ctrl+C` 强制结束。

### 2. 前端

```powershell
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

浏览器访问：<http://127.0.0.1:3000>

默认登录：`director` / `root123`（seed 演示账号；导演可在用户管理页创建更多账号）。

## 环境变量

### 前端 `.env.local`

```env
# 仅供 Next.js 服务端组件 / Route Handler 直连 FastAPI。
# 浏览器端请求走同源 /api/v1，由 route handler 转发 session，请勿改为直连 :8000。
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

### 后端 `.env`

```env
APP_ENV=development
APP_NAME=video-sop-editor-api
APP_HOST=127.0.0.1
APP_PORT=8000
APP_GRACEFUL_SHUTDOWN_SEC=5
DATABASE_URL=sqlite:///./video_sop.db
STORAGE_DIR=./storage

# 生产环境必填：用于加密 LLM API Key（migration 009）
# 更换后已加密的 Key 将无法解密，需在设置页重新保存 Provider 配置
APP_SECRET_KEY=change-me-to-a-long-random-string

# 可选：环境变量级 LLM 兜底（优先使用 DB Provider 配置）
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

## 部署与升级注意

1. **数据库迁移**：启动时自动执行 `app/migrations/runner.py`（当前至 **011**）。旧库直接启动即可升级；新库运行 `python init_db.py`。
2. **`APP_SECRET_KEY`**：生产必须设置稳定随机串。未设置时 LLM Key 加密功能受限；**更换密钥后需导演在 LLM 设置页重新保存 API Key**。
3. **Session 升级（migration 008）**：若从无二期的旧库升级，已有用户需 **重新登录** 获取新 Session Token。
4. **音频上传**：非 WAV 格式需系统 PATH 可调用 `ffmpeg`。
5. **BGM 工作流**：分镜解锁需完成 BGM 推荐 → 选定 → 上传识别（`bgmPhase: analyzed`）。

## 回归测试

依赖分三层：**Python 测后端**（`backend/requirements.txt`）、**Node 测前端单元**（`frontend/package.json`）、**Playwright 测 E2E**（根目录 `package.json`）。Vitest / Playwright **不在** `requirements.txt` 里。

### 后端（pytest）

```powershell
cd backend
pip install -r requirements.txt
python -m pytest tests/ -q
python -m pytest tests/test_llm_routes.py tests/test_llm_gateway.py tests/test_llm_model_catalog.py tests/test_llm_stream.py -q
python -m pytest tests/test_regression_sprint11.py -q
```

### 前端 workflow 脚本

```powershell
cd ..
node scripts/verify-workflow.mjs
```

### 前端单元测试（Vitest）

```powershell
cd frontend
npm install
npm run test:unit
```

### E2E（Playwright）

Playwright 在**仓库根目录**安装；首次需下载 Chromium。测试会自动拉起后端（`8000`）与前端 dev（`3000`），或使用已运行的实例（本地开发时 `reuseExistingServer`）。

```powershell
cd ..   # 仓库根目录
npm install
npx playwright install chromium
npm run test:e2e
```

| 文档 | 范围 |
|------|------|
| [`docs/regression-sprint3.md`](docs/regression-sprint3.md) | 主流程 API |
| [`docs/regression-sprint5.md`](docs/regression-sprint5.md) | LLM / SSE |
| [`docs/regression-sprint9.md`](docs/regression-sprint9.md) | 交互统一 |
| [`docs/regression-sprint10.md`](docs/regression-sprint10.md) | 二期验收 |
| [`docs/regression-sprint11.md`](docs/regression-sprint11.md) | lifespan、节拍网格、E2E |

## 文档索引

- 三期总控：[`docs/phase3-master.md`](docs/phase3-master.md)
- 三期清单：[`docs/phase3-checklist.md`](docs/phase3-checklist.md)
- 二期总控：[`docs/phase2-master.md`](docs/phase2-master.md)
- 二期清单：[`docs/phase2-checklist.md`](docs/phase2-checklist.md)
- 三期 backlog：[`docs/phase3-backlog.md`](docs/phase3-backlog.md)
- API：[`docs/api.md`](docs/api.md)
- 迁移规范：[`docs/schema-migration.md`](docs/schema-migration.md)

## 开发约定

- 业务生成逻辑放在 `backend/app/services/`，前端通过 API 消费。
- Schema 变更必须追加编号 migration，并同步 `entities` / `schemas` / `api.md`。
- 修改中文源码前阅读 [`docs/encoding-guardrails.md`](docs/encoding-guardrails.md)。
- 建议安装 git hooks：`powershell -ExecutionPolicy Bypass -File scripts\install-git-hooks.ps1`
