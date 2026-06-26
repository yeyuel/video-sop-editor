# Sprint 9 回归清单 — 交互统一

## 目标

验证 Sprint 9 前端交互统一改动：共享时间输入、素材选择器分组、BlockingNotice / ToastNotice / ConfirmDialog 口径一致。

## 自动化

```powershell
# 工作流解锁（含 BGM analyzed 门禁）
node scripts/verify-workflow.mjs

# 后端主流程
cd backend
python -m pytest tests/ -q
```

## 手工 smoke（导演账号）

1. **素材列表**
   - 顶部「素材整理区」操作栏可见
   - 删除素材走 ConfirmDialog，成功后 Toast 提示
   - 卡片聚焦后 Enter 进入编辑

2. **素材编辑**
   - 建议时长使用统一校验（非法输入提示「请输入有效秒数，例如 1.5」）
   - Esc 返回列表；保存时 BlockingNotice

3. **主题页**
   - 已选主题置顶 + 「当前已选主题」标签
   - 候选主题在下方网格；错误用 clay banner

4. **分镜列表**
   - 删除镜头走 ConfirmDialog（非 window.confirm）
   - 校验 warning 用 Toast warning 色调
   - 卡片 Enter 进入编辑

5. **分镜编辑**
   - 开始/结束时间共用 TimeSecondsInput，超过目标时长有提示
   - 素材选择器按地点分组 + 搜索过滤
   - Esc 返回列表

## 共享组件

| 组件 | 路径 |
|------|------|
| TimeSecondsInput | `frontend/components/time-seconds-input.tsx` |
| AssetSelector | `frontend/components/asset-selector.tsx` |
| EmptyState / InlineErrorBanner / ConfirmDialog | `frontend/components/ui-primitives.tsx` |
| 时间校验工具 | `frontend/lib/time-input.ts` |

## 移除项

- `frontend/components/storyboard-client.tsx`（已由 list + segment editor 替代）
