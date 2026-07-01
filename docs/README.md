# 文档目录

当前 `docs` 目录用于沉淀一期交付结果、二期开发上下文和接口约束，后续继续以这里作为项目主文档入口。

## 核心文档

- `prd.md`：当前产品需求文档，按现网一期逻辑校准，并补充二期规划边界。
- `sop.md`：标准作业流程，强调素材录入、主题、节奏、分镜、导出之间的业务顺序。
- `api.md`：前后端接口文档，覆盖当前已实现的一期接口和已落地的二期能力接口。

## 阶段上下文

- `phase1-context.md`：一期当前实现状态压缩版，方便二期开发快速接入上下文。
- `phase2-master.md`：二期主控文档，定义目标、边界、优先级和实施顺序（**已关闭**）。
- `phase2-checklist.md`：二期执行检查清单，按 P0 / P1 / P2 与 Sprint 迭代跟踪落地。
- `phase3-master.md`：三期主控文档，含已锁定决策与 Sprint 11～18 路线（**已关闭**）。
- `phase3-checklist.md`：三期执行清单。
- `phase3-backlog.md`：四期需求池（三期移出项）。
- `regression-sprint3.md`：Sprint 3 关键路径回归测试说明与运行命令。
- `regression-sprint11.md`：Sprint 11 E2E / lifespan / 节拍网格回归。
- `regression-sprint18.md`：Sprint 18 三期验收冻结与四决策表。
- `schema-migration.md`：数据库 migration 规范与字段变更检查清单。

## 能力专项

- `phase2-llm-integration-standard.md`：LLM 接入统一规范，包含 Provider、鉴权、配置和安全边界。
- `encoding-guardrails.md`：编码与防乱码约束，说明 UTF-8、PowerShell 脚本编码和乱码扫描方式。

## 使用建议

- 看业务逻辑先读 `prd.md` 和 `sop.md`。
- 看字段和接口先读 `api.md`。
- 开始三期开发前，先读 `phase3-master.md` 和 `phase3-checklist.md`。
- 开始修改中文文案、文档或脚本前，先读 `encoding-guardrails.md`，避免把乱码重新写回仓库。
