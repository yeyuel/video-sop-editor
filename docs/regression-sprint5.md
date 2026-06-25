# Sprint 5 回归测试说明

## 1. 目的

覆盖 `phase2-checklist.md` Sprint 5（LLM 网关标准化）的最小可重复回归，与 Sprint 3 脚本互补。

## 2. 后端 LLM / 流式回归

在 `backend/` 目录执行：

```powershell
pip install -r requirements.txt
python -m pytest tests/test_llm_routes.py tests/test_llm_gateway.py tests/test_llm_model_catalog.py tests/test_llm_stream.py -q
```

| 模块 | 测试文件 | 覆盖点 |
|------|----------|--------|
| Provider 配置 | `test_llm_routes.py` | 列表、保存、激活、连通性、OAuth stub |
| Gateway | `test_llm_gateway.py` | Auth、max_tokens、Kimi thinking 关闭、JSON 解析 |
| 模型目录 | `test_llm_model_catalog.py` | Kimi K2 别名、temperature、response_format |
| SSE 流式 | `test_llm_stream.py` | 主题 / 分镜 / 导出 / 节奏 stream 完成事件 |

未配置真实 API Key 时，业务 stream 测试预期 `llmStatus` 为 `fallback_rule` 或 `not_configured`，接口仍应返回 `complete` 事件。

## 3. 全量回归（推荐发布前）

```powershell
cd backend
python -m pytest tests/ -q

cd ..
node scripts/verify-workflow.mjs
```

## 4. 手动抽检（可选）

- 设置 → LLM：保存 Kimi / OpenAI 配置 → **设为生效** → 测试连通性
- 主题 / 分镜 / 节奏 / 导出：触发 LLM 操作，确认进度遮罩与 toast meta 一致
- Kimi K2.6：确认不再出现 temperature 400 或空 content 兜底

## 5. LLM 兜底口径

| llmStatus | 含义 | 用户侧表现 |
|-----------|------|------------|
| `success` | 模型返回有效 JSON | 正常 LLM 结果 |
| `fallback_rule` | 调用失败或解析失败 | 规则生成 + 警告 toast |
| `not_configured` | 未配置 Key | 规则生成 + 配置提示 |
| `timeout` | 超过 `LLM_TIMEOUT_SEC` | 规则生成 + 超时提示 |
| `empty_response` / `parse_error` | 无正文或 JSON 无效 | 规则生成 + 解析提示 |

## 6. 最近验证

- 日期：2026-06-24
- 范围：Sprint 5 收尾（文档 + stream 测试 + Kimi 兼容）
