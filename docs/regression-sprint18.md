# Sprint 18 回归清单 — 三期验收冻结

## 目标

Sprint 18：汇总 Sprint 11～17 交付，按 `phase3-master.md` §10 关闭标准冻结回归；E2E 双角色 smoke；文档与 backlog 标四期。

## 自动化

```powershell
cd backend
python -m pytest tests/ -q
python -m pytest tests/test_regression_sprint18.py -q

cd ../frontend
npm run test:unit

cd ..
node scripts/verify-workflow.mjs
npx playwright install chromium
npm run test:e2e
```

## 四决策验收表

| 决策 | 结论 | 自动化验证 |
|------|------|-----------|
| **1 剪辑侧开放** | 剪辑可读写项目内工作流，不可用户/LLM 管理 | `test_regression_sprint12.py`；`test_regression_sprint18.py::test_decision1_*`；`e2e/editor-smoke.spec.ts` |
| **2 LLM Vision** | Mock 分析预填 ≥3 字段 | `test_regression_sprint14.py`；`test_regression_sprint18.py::test_decision2_*` |
| **3 镜头复用** | `allowAssetReuse` 默认关，可开关 | `test_regression_sprint15.py`；`test_regression_sprint18.py::test_decision3_*` |
| **4 OAuth** | OpenAI OAuth Mock 授权成功；Google 订阅 UI 隐藏非阻塞 | `test_regression_sprint16.py`；`test_regression_sprint18.py::test_decision4_*` |
| **5 单机 SQLite** | 无 Redis 依赖；Session 落 SQLite | `test_regression_sprint18.py::test_decision5_*` |

## Sprint 18 专项

| 项 | 验证方式 |
|----|---------|
| Migration 冻结 | `test_regression_sprint18.py::test_phase3_migrations_frozen_at_latest_version` |
| 导出 JSON round-trip dry-run | `test_regression_sprint18.py::test_phase3_export_json_round_trip` |
| 剪映草稿写入 + 悠然体 font id | `test_regression_sprint18.py::test_phase3_capcut_deploy_writes_draft_files` |
| Shutdown 不污染 SSE | `conftest` autouse `reset_shutdown_state`；全量 pytest 含 Sprint 14 Vision |
| 导演 E2E | `e2e/director-smoke.spec.ts` |
| 剪辑 E2E | `e2e/editor-smoke.spec.ts` |
| 文档关闭 | `phase3-master.md` / `phase3-checklist.md` / `phase3-backlog.md` |

## 手工 smoke（可选）

1. 导演登录 → 导出页「写入剪映草稿目录」→ 剪映打开粗剪时间线
2. 素材页 Vision Mock（`VISION_USE_MOCK=true`）→ 预填 → 保存
3. LLM 设置 → OpenAI Platform OAuth Mock 连接 → 连通性测试

## 最近验证

- 日期：2026-06-21
- 结果：backend **208 passed**；`verify-workflow` 7 checks；Playwright 需本地 `npx playwright install chromium` 后跑 2 条 smoke
