# Windows 台式机本地部署操作手册

## 1. 部署结构

本方案把 GitHub 仓库、生产代码和业务数据分开：

```text
D:\vibe-coding\video-sop-editor     开发仓库
D:\video-sop-production
├─ releases                         历史发布版本
├─ current                          指向当前版本的目录联接
├─ config                           不进入 Git 的生产配置
├─ data
│  ├─ video_sop.db                  SQLite 数据库
│  ├─ storage                       上传音频及生成文件
│  └─ backups                       自动数据库备份
├─ logs                             前后端运行日志
└─ state                            当前及上一版本记录
```

前后端由隐藏的 Windows 计划任务托管，不显示或保留命令行窗口。电脑重启后，在当前
Windows 用户登录桌面时自动启动；登录前不会启动。为了与同一台机器上的开发环境错开，
端口默认分配为：

| 环境 | 前端 | 后端 |
| --- | --- | --- |
| 开发环境 | `3000` | `8000` |
| 生产环境 | `3100` | `8100` |

生产后端只监听 `127.0.0.1:8100`，生产前端监听 `0.0.0.0:3100`。

## 2. 一次性安装依赖

台式机需要安装：

- Git
- Python 3.12 x64
- Node.js 22 LTS
- ffmpeg，并确保 `ffmpeg.exe` 在系统 `PATH`
- Windows PowerShell 5.1 或 PowerShell 7

在新的 PowerShell 窗口验证：

```powershell
git --version
python --version
node --version
npm.cmd --version
ffmpeg -version
```

如果 PowerShell 禁止执行脚本，后续命令统一使用：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <脚本路径> <参数>
```

## 3. 首次在本机直接部署

### 3.1 更新仓库

```powershell
cd D:\vibe-coding\video-sop-editor
git pull origin main
```

### 3.2 初始化生产目录

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Initialize-Deployment.ps1 `
  -DeployRoot "D:\video-sop-production"
```

脚本会创建稳定的 `APP_SECRET_KEY`，不会修改开发环境的 `.env`。

### 3.3 检查生产配置

编辑：

```text
D:\video-sop-production\config\backend.env
D:\video-sop-production\config\frontend.env.local
D:\video-sop-production\config\deployment.env
```

至少确认：

- `APP_SECRET_KEY` 已生成，后续不要随意更换。
- `DATABASE_URL` 指向 `D:/video-sop-production/data/video_sop.db`。
- `STORAGE_DIR` 指向 `D:/video-sop-production/data/storage`。
- `deployment.env` 默认使用 `FRONTEND_PORT=3100`、`BACKEND_PORT=8100`。
- OAuth、Vision 或环境变量级 LLM Key 按实际使用方式填写。
- 数据库里配置的 Provider Key 会使用 `APP_SECRET_KEY` 加密，不需要写入 GitHub。

### 3.4 执行第一次部署

建议首次在当前 Windows 用户登录状态下执行：

```powershell
cd D:\vibe-coding\video-sop-editor
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Deploy.ps1 `
  -DeployRoot "D:\video-sop-production" `
  -RegisterTasks `
  -RunTests
```

第一次执行会安装 Python 和 Node 依赖，耗时可能为 5～20 分钟。以后 CI 已通过时可省略
`-RunTests`。

部署成功后访问：

```text
http://127.0.0.1:3100
```

部署注册的 `VideoSopEditor-Backend` 和 `VideoSopEditor-Frontend` 任务具有以下行为：

- 当前 Windows 用户每次登录时自动启动。
- 后台隐藏运行，不出现常驻 PowerShell/命令行窗口。
- 进程异常退出后最多自动重试 3 次，每次间隔 1 分钟。
- 服务运行期间任务状态保持为 `Running`，便于检测和停止完整进程树。

## 4. 日常本地操作

### 查看状态

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Get-AppStatus.ps1
```

### 停止

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Stop-App.ps1
```

### 启动

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Start-App.ps1
```

### 查看日志

```powershell
Get-Content D:\video-sop-production\logs\backend.stdout.log -Encoding utf8 -Tail 100 -Wait
Get-Content D:\video-sop-production\logs\backend.stderr.log -Encoding utf8 -Tail 100 -Wait
Get-Content D:\video-sop-production\logs\frontend.stdout.log -Encoding utf8 -Tail 100 -Wait
Get-Content D:\video-sop-production\logs\frontend.stderr.log -Encoding utf8 -Tail 100 -Wait
```

### 发布当前仓库版本

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Deploy.ps1 `
  -DeployRoot "D:\video-sop-production" `
  -RegisterTasks
```

部署过程会：

1. 在新 release 中安装依赖并构建前端，当前版本继续运行。
2. 构建成功后停止服务。
3. 使用 SQLite Backup API 创建一致性备份。
4. 切换 `current` 到新版本。
5. 启动前后端并检查两个 HTTP 地址。
6. 启动失败时自动切回上一版本并恢复部署前数据库。

## 5. 手动回滚

只回滚代码、不回滚数据库：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Rollback.ps1
```

如果新版本执行了不兼容的数据库迁移，应同时指定部署前备份：

```powershell
Get-ChildItem D:\video-sop-production\data\backups | Sort-Object LastWriteTime -Descending

powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  .\scripts\windows-deploy\Rollback.ps1 `
  -RestoreDatabaseFrom "D:\video-sop-production\data\backups\具体备份.db"
```

回滚前脚本还会再创建一份安全备份。

## 6. 配置 GitHub Self-hosted Runner

仓库建议保持 Private。不要让来自 Fork 或不可信分支的 Workflow 使用台式机 Runner。

1. 打开 GitHub 仓库。
2. 进入 `Settings → Actions → Runners`。
3. 点击 `New self-hosted runner`。
4. 选择 `Windows`、`x64`。
5. 在管理员 PowerShell 中进入 `C:\actions-runner`，逐条执行 GitHub 页面生成的命令。
6. 配置 Runner 时增加标签 `video-sop-prod`。
7. 选择安装为 Windows 服务。
8. 服务账号使用日常登录台式机、能够访问素材和剪映草稿的 Windows 用户，不使用
   `Network Service`。

注册完成后检查：

```powershell
Get-Service "actions.runner.*"
```

GitHub Runner 页面应显示 `Idle`，标签应包含：

```text
self-hosted, windows, x64, video-sop-prod
```

Runner 注册 Token 由 GitHub 页面临时生成并在一小时后过期，不需要保存到仓库。

## 7. 配置 GitHub Actions

仓库已包含：

```text
.github/workflows/ci.yml
.github/workflows/deploy-local.yml
```

### 7.1 配置部署目录变量

进入：

```text
GitHub → Settings → Secrets and variables → Actions → Variables
```

新增 Repository variable：

```text
DEPLOY_ROOT = D:\video-sop-production
```

生产 `.env` 和业务数据库保留在台式机，不需要创建 GitHub Secret。

### 7.2 验证 CI

推送到 `main` 后，进入 GitHub `Actions → CI`，确认：

- Backend tests 通过。
- Frontend tests and build 通过。
- Encoding guard 通过。

### 7.3 从 GitHub 发布到台式机

1. 进入 `Actions → Deploy to local desktop`。
2. 点击 `Run workflow`。
3. Branch 选择 `main`。
4. 首次可勾选重新运行完整测试，后续通常保持关闭。
5. 点击运行。

CD 只接受 `main`，同一时间只允许一个部署任务。台式机离线时任务会排队，Runner 上线后继续。

## 8. 局域网访问

先用 `ipconfig` 找到台式机 IPv4 地址，例如 `192.168.3.10`。管理员 PowerShell 执行：

```powershell
New-NetFirewallRule `
  -DisplayName "Video SOP Editor Frontend" `
  -Direction Inbound `
  -Protocol TCP `
  -LocalPort 3100 `
  -Action Allow `
  -Profile Private
```

同一局域网设备访问：

```text
http://192.168.3.10:3100
```

不要开放开发后端 `8000` 或生产后端 `8100`。如需从公网访问，应增加 HTTPS 反向代理、正式域名和访问控制，不要直接做路由器端口映射。

## 9. 修改生产端口

只需要编辑：

```text
D:\video-sop-production\config\deployment.env
```

例如：

```env
BACKEND_PORT=8200
FRONTEND_PORT=3200
```

然后重新执行 `Deploy.ps1`。部署脚本会在前端构建、后端启动、OAuth 回调和健康检查中统一使用
新端口。不要只修改 `backend.env` 或 `frontend.env.local`，避免配置不一致。

## 10. 故障定位

| 现象 | 检查方式 |
| --- | --- |
| GitHub CD 一直排队 | Runner 是否 Online；是否有 `video-sop-prod` 标签 |
| 计划任务启动失败 | `Get-AppStatus.ps1`、Windows 任务计划程序历史记录 |
| 后端不可用 | `logs/backend.log`、`APP_SECRET_KEY`、数据库路径、ffmpeg PATH |
| 前端不可用 | `logs/frontend.log`、`.next` 是否构建成功、3100 端口是否占用 |
| 剪映草稿写入失败 | Runner/计划任务账号是否为日常 Windows 用户；剪映是否正在占用草稿 |
| 新版本启动失败 | 查看 Actions 日志；脚本应自动恢复上一 release |
