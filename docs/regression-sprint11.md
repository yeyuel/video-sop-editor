# Sprint 11 回归清单 — 工程基线

## 目标

三期 Sprint 11：FastAPI lifespan、前端节拍吸附网格对齐、Playwright E2E smoke、文档同步。

## 自动化

```powershell
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_regression_sprint11.py -q

cd ../frontend
npm install
npm run test:unit

cd ..
npm install
npx playwright install chromium
npm run test:e2e
node scripts/verify-workflow.mjs
```

## Sprint 11 专项

| 项 | 验证方式 |
|----|---------|
| FastAPI lifespan | `test_regression_sprint11.py::test_app_lifespan_boots_and_seeds_demo_data`；启动无 `on_event` 弃用 |
| 节拍吸附网格 | `frontend/lib/storyboard-beat-grid.test.ts`；编辑页使用 `resolveSnapBeatPointsForSegment` |
| 导演 E2E smoke | `e2e/director-smoke.spec.ts` |
| 文档 | `phase3-checklist.md` Sprint 11 勾选 |

## 手工 smoke（可选）

- 分镜编辑页：beat_2 项目吸附到细网格而非 coarse `beatPoints`
- E2E 首次运行需 `npx playwright install chromium`

## 最近验证

- 日期：2026-06-27
- 结果：backend 101 passed；frontend vitest 5 passed；playwright 1 passed；verify-workflow 7 checks
