# Sprint 12 回归清单 — 剪辑侧开放 + RBAC MVP

## 目标

Sprint 12（决策 1）：剪辑登录、角色门禁、项目 API 鉴权、LLM 审计日志、导演/剪辑 E2E。

## 自动化

```powershell
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_regression_sprint12.py -q

cd ../frontend
npm install
npm run test:unit

cd ..
npm install
npx playwright install chromium
npm run test:e2e
node scripts/verify-workflow.mjs
```

## Sprint 12 专项

| 项 | 验证方式 |
|----|---------|
| 登录选项 API | `test_regression_sprint12.py::test_login_options_lists_enabled_users` |
| 项目路由鉴权 | `test_regression_sprint12.py::test_project_routes_require_auth` |
| 剪辑项目访问 | `test_regression_sprint12.py::test_editor_can_access_project_workspace` |
| 剪辑禁删项目 | `test_regression_sprint12.py::test_editor_cannot_delete_project` |
| LLM 审计 | `test_regression_sprint12.py::test_theme_llm_call_writes_audit_log` |
| 导演 E2E | `e2e/director-smoke.spec.ts` |
| 剪辑 E2E | `e2e/editor-smoke.spec.ts` |
| Demo 账号 | 导演 `director` / `root123`；剪辑 `editor` / `edit123` |

## 手工 smoke（可选）

- 导演在用户管理页创建剪辑账号并开关「允许登录」
- 剪辑登录后 Topbar 显示角色说明，无法进入 LLM 配置与用户管理
- 导演在 LLM 配置页查看最近调用审计列表

## 最近验证

- 日期：2026-06-21
- 结果：backend 110 passed；frontend vitest 5 passed；playwright 2 passed；verify-workflow 7 checks
