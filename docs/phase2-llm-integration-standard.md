# 二期 LLM 接入标准

## 1. 文档目的

本文档用于约束二期 LLM 能力接入方式，避免把当前实现绑定在单一厂商或单一认证模式上。

适用范围：

- 主题建议
- 分镜建议
- 导出建议
- 后续可能扩展的节奏建议、素材分析建议

默认结论：

- 业务层面按“LLM 能力”设计
- 认证层面按“多模式授权”设计
- 厂商层面按“可插拔 provider”设计

## 2. 设计原则

- 不把产品能力绑定为单一 OpenAI 命名体系
- 不把“网页产品可登录”误判为“官方开放能力可接入”
- 只接入厂商正式开放的 API 或授权协议
- 上层业务不直接感知具体厂商，只感知统一 LLM Gateway
- 任一 provider 不可用时，应允许 fallback 到规则逻辑或手工输入

## 3. 标准接入模式

### 3.1 API Key 模式

适用条件：

- 厂商提供官方 API Key
- 厂商提供明确服务端调用协议
- 厂商接口兼容 OpenAI 风格，或可通过适配层转换

适用示例：

- OpenAI API
- Kimi 开放平台
- GLM 开放平台
- DeepSeek 开放平台

要求：

- API Key 只保存在后端
- 前端不可直接持有密钥
- 统一保存 `provider`、`base_url`、`model`

### 3.2 OAuth 浏览器跳转授权模式

适用条件：

- 厂商提供官方 OAuth 2.0 或 OIDC
- 用户需要通过浏览器完成登录与授权

推荐流程：

1. 用户点击“连接提供商”
2. 系统生成授权链接
3. 浏览器跳转厂商授权页
4. 用户登录并确认授权
5. 回调到后端 callback 地址
6. 后端用授权码换取 access token / refresh token
7. 持久化授权状态

推荐协议：

- Authorization Code
- PKCE

要求：

- 支持 refresh token
- 支持 token 过期检查
- 支持授权失效后的重新授权

### 3.3 Device Code 模式

适用条件：

- 厂商提供 Device Code Flow
- 当前端不方便直接完成网页登录
- 适合桌面端或受限终端

推荐流程：

1. 系统申请 device code
2. 返回 `verification_uri` 和 `user_code`
3. 用户在浏览器中手工完成授权
4. 后端按轮询周期换取 token
5. 成功后写入授权状态

要求：

- 支持轮询超时
- 支持取消授权流程
- 支持失败回滚到未授权状态

## 4. 明确不支持的情况

以下情况不视为正式可接入：

- 只有网页产品订阅，但没有官方 API
- 只有网页登录，没有开放 OAuth / OIDC / Device Code
- 依赖抓取 cookie、session、网页本地存储
- 依赖模拟网页登录后窃取凭证

说明：

- “我能登录这个网页产品”不等于“系统可以正式接入这个能力”
- 是否支持接入，以厂商官方开放协议为准

## 5. 统一配置模型

建议统一使用以下字段：

- `provider_id`
- `provider_name`
- `auth_type`
- `base_url`
- `model`
- `api_key`
- `client_id`
- `client_secret`
- `scopes`
- `callback_url`
- `access_token`
- `refresh_token`
- `expires_at`
- `status`

字段约束：

- `auth_type` 枚举：`api_key`、`oauth`、`device_code`
- `status` 枚举：`configured`、`authorized`、`expired`、`invalid`

说明：

- 若为 `api_key` 模式，则 `api_key` 必填
- 若为 `oauth` 模式，则 `client_id`、`callback_url` 必填
- 若为 `device_code` 模式，则应保存本次授权轮询状态

## 6. 服务分层建议

建议拆成三层：

### 6.1 Provider Registry

职责：

- 登记 provider 元数据
- 声明支持的认证模式
- 声明默认 `base_url`
- 声明是否兼容 OpenAI-style 接口

### 6.2 Auth Service

职责：

- 处理 API Key 校验
- 处理 OAuth 授权与回调
- 处理 Device Code 申请与轮询
- 统一管理 token 生命周期

### 6.3 LLM Gateway

职责：

- 向主题、分镜、导出等上层模块暴露统一接口
- 根据 provider 配置路由到底层适配器
- 屏蔽不同厂商的认证和协议差异

上层业务只调用：

- `generate_theme_suggestions`
- `generate_storyboard_suggestions`
- `generate_export_suggestions`

## 7. 与当前实现的关系

当前代码状态：

- 已具备通用 `LLM_*` 配置起点
- 当前调用层仍以 OpenAI-compatible 协议优先
- 当前更适合承接 API Key 模式

后续推荐演进顺序：

1. 继续保留当前 `LLM_*` 配置
2. 增加 provider registry
3. 增加 OAuth callback 与 token 持久化
4. 增加 Device Code 流程
5. 最后增加多 provider 切换 UI

## 8. 二期开发约束

- 业务模块不得直接写死 `OPENAI_*`
- 不允许把认证逻辑散落在主题、分镜、导出模块内部
- 所有 LLM provider 都必须先过“官方协议可接入性确认”
- 新 provider 上线前，必须明确它属于 `api_key`、`oauth`、`device_code` 中哪一种
- 任一 provider 不可用时，必须允许回退到规则逻辑或手工方案

## 9. 当前建议

对当前项目，建议默认优先级如下：

1. 先把 API Key 模式做稳
2. 再补 OAuth 浏览器跳转模式
3. 最后补 Device Code 模式

原因：

- API Key 模式最容易尽快支撑 Kimi、GLM、DeepSeek 一类开放平台
- OAuth 更适合未来接官方授权能力
- Device Code 是增强项，但架构上应先预留
