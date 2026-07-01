"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useState, useTransition } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import {
  activateLlmProvider,
  getLlmAuditLogs,
  getLlmProviderModels,
  getLlmProviderStatus,
  getLlmProviders,
  getLlmStatus,
  pollLlmSubscriptionOAuth,
  revokeLlmOAuth,
  revokeLlmSubscriptionOAuth,
  saveLlmProviderConfig,
  startLlmOAuth,
  startLlmSubscriptionOAuth,
  testActiveLlmProvider,
  testLlmProvider
} from "@/lib/browser-api";
import type { LlmAuditLog } from "@/lib/browser-api";
import type { LlmModelOption, LlmProvider, LlmStatus, LlmTestResult } from "@/lib/llm-status";

type LlmAuthType = "api_key" | "oauth" | "codex_oauth" | "gemini_subscription";

/** Hidden in UI; backend routes remain available for future re-enable. */
const HIDDEN_UI_AUTH_TYPES = new Set<LlmAuthType>(["oauth", "gemini_subscription"]);

function isHiddenUiAuthType(authType: LlmAuthType) {
  return HIDDEN_UI_AUTH_TYPES.has(authType);
}

function resolveVisibleAuthType(authType: LlmAuthType): LlmAuthType {
  if (!isHiddenUiAuthType(authType)) {
    return authType;
  }
  return "api_key";
}

const PROVIDER_SUBTITLE_OVERRIDES: Record<string, string> = {
  openai: "官方 API · ChatGPT 登录 (Codex)",
  google: "Gemini API Key"
};

/** Hidden in provider sidebar; backend registry and APIs remain available. */
const HIDDEN_UI_PROVIDER_IDS = new Set(["google", "deepseek", "glm"]);

function isHiddenUiProvider(providerId: string) {
  return HIDDEN_UI_PROVIDER_IDS.has(providerId);
}

function filterVisibleProviders(providers: LlmProvider[]) {
  return providers.filter((provider) => !isHiddenUiProvider(provider.providerId));
}

function resolveVisibleProviderId(providerId: string, providers: LlmProvider[]) {
  if (providerId && !isHiddenUiProvider(providerId)) {
    return providerId;
  }
  const visible = filterVisibleProviders(providers);
  return (
    visible.find((item) => item.isActive)?.providerId ??
    visible[0]?.providerId ??
    ""
  );
}

function normalizeAuthType(value: string): LlmAuthType {
  if (
    value === "oauth" ||
    value === "codex_oauth" ||
    value === "gemini_subscription"
  ) {
    return value;
  }
  return "api_key";
}

function isOAuthLikeAuthType(authType: LlmAuthType) {
  return authType === "oauth" || authType === "codex_oauth" || authType === "gemini_subscription";
}

const STATUS_LABELS: Record<string, string> = {
  configured: "已配置",
  not_configured: "未配置",
  authorized: "已授权",
  expired: "已过期",
  invalid: "无效"
};

function statusBadgeClass(status: string) {
  if (status === "configured" || status === "authorized") {
    return "border-pine/20 bg-mist text-pine";
  }
  return "border-clay/15 bg-[#fff5ef] text-clay";
}

function recommendedModel(provider?: LlmProvider | null, authType: LlmAuthType = "api_key") {
  if (!provider) {
    return "";
  }
  const fromOptions = provider.models.find((item) => item.recommended)?.modelId;
  if (authType === "codex_oauth") {
    return "gpt-5.5";
  }
  if (authType === "gemini_subscription") {
    return "gemini-2.5-pro";
  }
  return fromOptions ?? provider.defaultModel;
}

function isKnownModel(modelId: string, provider?: LlmProvider | null) {
  if (!modelId.trim()) {
    return false;
  }
  return Boolean(provider?.models.some((item) => item.modelId === modelId));
}

const AUDIT_STATUS_LABELS: Record<string, string> = {
  ok: "成功",
  fallback: "规则回退",
  error: "失败",
  unknown: "未知"
};

function formatAuditEndpoint(endpoint: string): string {
  const path = endpoint.replace(/^\/projects\/[^/]+\//, "");
  const labels: Record<string, string> = {
    "themes/generate-llm": "主题 LLM 生成",
    "themes/generate-llm/stream": "主题 LLM 生成（流式）",
    "storyboard:generate-llm": "分镜 LLM 生成",
    "storyboard/generate-llm/stream": "分镜 LLM 生成（流式）",
    "export-plan:suggest": "导出方案建议",
    "export-plan/suggest/stream": "导出方案建议（流式）",
    "rhythm-plan/bgm-recommend": "BGM 推荐",
    "rhythm-plan/bgm-recommend/stream": "BGM 推荐（流式）",
    "vision-analyze/stream": "素材 Vision 分析"
  };
  return labels[path] ?? path.replace(/\//g, " · ");
}

function formatAuditTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false
    });
  } catch {
    return iso;
  }
}

function auditStatusClass(status: string) {
  if (status === "ok") {
    return "border-pine/20 bg-mist text-pine";
  }
  if (status === "fallback") {
    return "border-amber-200/80 bg-amber-50 text-amber-900";
  }
  return "border-clay/15 bg-[#fff5ef] text-clay";
}

function LlmAuditSection({ logs }: { logs: LlmAuditLog[] }) {
  return (
    <section className="surface-panel p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Audit Log</p>
          <h2 className="mt-2 text-xl font-semibold text-ink">最近 LLM 调用</h2>
          <p className="mt-1 text-sm text-ink/60">导演可见，SQLite 存储，最多展示 10 条。</p>
        </div>
        <span className="text-xs text-ink/45">{logs.length} 条记录</span>
      </div>

      {logs.length === 0 ? (
        <p className="mt-6 rounded-2xl border border-dashed border-pine/15 bg-sand/30 px-4 py-8 text-center text-sm text-ink/55">
          暂无调用记录。在项目内使用 LLM 建议后，会在此显示。
        </p>
      ) : (
        <div className="mt-5 overflow-x-auto rounded-2xl border border-pine/10">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="border-b border-pine/10 bg-sand/40 text-xs uppercase tracking-wide text-ink/55">
                <th className="px-4 py-3 font-medium">时间</th>
                <th className="px-4 py-3 font-medium">操作</th>
                <th className="px-4 py-3 font-medium">模型</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">说明</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-pine/8 bg-white/70">
              {logs.map((log) => (
                <tr key={log.id} className="transition hover:bg-mist/40">
                  <td className="whitespace-nowrap px-4 py-3 text-xs tabular-nums text-ink/60">
                    {formatAuditTime(log.createdAt)}
                  </td>
                  <td className="px-4 py-3 font-medium text-ink">
                    {formatAuditEndpoint(log.endpoint)}
                  </td>
                  <td className="max-w-[8rem] truncate px-4 py-3 text-xs text-ink/65" title={log.model}>
                    {log.model || "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={[
                        "inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium",
                        auditStatusClass(log.status)
                      ].join(" ")}
                    >
                      {AUDIT_STATUS_LABELS[log.status] ?? log.status}
                    </span>
                  </td>
                  <td className="hidden max-w-xs truncate px-4 py-3 text-xs text-ink/55 md:table-cell">
                    {log.message || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function LlmSettingsClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [activeStatus, setActiveStatus] = useState<LlmStatus | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [providerStatus, setProviderStatus] = useState<LlmStatus | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [authType, setAuthType] = useState<LlmAuthType>("api_key");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();
  const [testResult, setTestResult] = useState<LlmTestResult | null>(null);
  const [useCustomModel, setUseCustomModel] = useState(false);
  const [auditLogs, setAuditLogs] = useState<LlmAuditLog[]>([]);
  const [modelOptions, setModelOptions] = useState<LlmModelOption[]>([]);
  const [liveModelsMessage, setLiveModelsMessage] = useState("");

  const loadProviderForm = useCallback(async (providerId: string, providerList: LlmProvider[], nextAuthType?: LlmAuthType) => {
    const status = await getLlmProviderStatus(providerId);
    const provider = providerList.find((item) => item.providerId === providerId);
    const resolvedAuthType = resolveVisibleAuthType(
      nextAuthType ?? normalizeAuthType(status.authType)
    );
    const nextModel = status.model || recommendedModel(provider);
    setProviderStatus(status);
    setAuthType(resolvedAuthType);
    setBaseUrl(status.baseUrl);
    setUseCustomModel(!isKnownModel(nextModel, provider));
    setModel(nextModel);
    setApiKey("");

    let options = provider?.models ?? [];
    setLiveModelsMessage("");
    const useLiveModels =
      status.configured &&
      resolvedAuthType !== "codex_oauth" &&
      resolvedAuthType !== "gemini_subscription";
    try {
      options = await getLlmProviderModels(providerId, {
        live: useLiveModels,
        authType: resolvedAuthType
      });
      if (!useLiveModels && resolvedAuthType !== "api_key") {
        setLiveModelsMessage("订阅/Platform OAuth 模式使用专用模型目录。");
      }
    } catch (loadError) {
      setLiveModelsMessage(
        loadError instanceof Error ? loadError.message : "无法获取模型列表，已使用静态列表。"
      );
    }
    setModelOptions(options);
    const recommended = options.find((item) => item.recommended)?.modelId;
    if (
      recommended &&
      (resolvedAuthType === "codex_oauth" || resolvedAuthType === "gemini_subscription") &&
      !options.some((item) => item.modelId === nextModel)
    ) {
      setModel(recommended);
      setUseCustomModel(false);
    }
  }, []);

  const refreshAll = useCallback(
    async (providerId?: string) => {
      const [providerList, active, logs] = await Promise.all([
        getLlmProviders(),
        getLlmStatus(),
        getLlmAuditLogs(10)
      ]);
      setProviders(providerList);
      setActiveStatus(active);
      setAuditLogs(logs);
      const targetId = resolveVisibleProviderId(
        providerId ??
          providerList.find((item) => item.isActive)?.providerId ??
          active.providerId ??
          "",
        providerList
      );
      if (targetId) {
        setSelectedProviderId(targetId);
        await loadProviderForm(targetId, providerList);
      }
    },
    [loadProviderForm]
  );

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      setLoading(true);
      setError("");
      try {
        const [providerList, active, logs] = await Promise.all([
          getLlmProviders(),
          getLlmStatus(),
          getLlmAuditLogs(10)
        ]);
        if (cancelled) {
          return;
        }
        setProviders(providerList);
        setActiveStatus(active);
        setAuditLogs(logs);
        const initialId = resolveVisibleProviderId(
          providerList.find((item) => item.isActive)?.providerId ??
            active.providerId ??
            providerList[0]?.providerId ??
            "",
          providerList
        );
        setSelectedProviderId(initialId);
        if (initialId) {
          await loadProviderForm(initialId, providerList);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "加载 LLM 配置失败。");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadProviderForm]);

  useEffect(() => {
    if (searchParams.get("oauth") !== "success") {
      return;
    }
    setNotice({
      title: "OAuth 授权成功",
      message: "Provider 连接状态已更新，可测试连接并设为生效。",
      tone: "success"
    });
    router.replace("/settings/llm");
  }, [router, searchParams]);

  useEffect(() => {
    if (!notice) {
      return;
    }
    const timer = window.setTimeout(() => setNotice(null), 2800);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function handleAuthTypeChange(nextAuthType: LlmAuthType) {
    const visibleAuthType = resolveVisibleAuthType(nextAuthType);
    setAuthType(visibleAuthType);
    setTestResult(null);
    if (!selectedProviderId) {
      return;
    }
    startTransition(async () => {
      try {
        await loadProviderForm(selectedProviderId, providers, visibleAuthType);
        const provider = providers.find((item) => item.providerId === selectedProviderId);
        const nextRecommended = recommendedModel(provider, nextAuthType);
        if (nextAuthType === "codex_oauth" || nextAuthType === "gemini_subscription") {
          setModel(nextRecommended);
          setUseCustomModel(false);
        }
      } catch (selectError) {
        setError(selectError instanceof Error ? selectError.message : "切换认证方式失败。");
      }
    });
  }

  function handleSelectProvider(providerId: string) {
    setSelectedProviderId(providerId);
    setTestResult(null);
    setError("");
    startTransition(async () => {
      try {
        await loadProviderForm(providerId, providers);
      } catch (selectError) {
        setError(selectError instanceof Error ? selectError.message : "加载 Provider 配置失败。");
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProviderId) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const saved = await saveLlmProviderConfig(selectedProviderId, {
          authType,
          baseUrl,
          model,
          apiKey: apiKey.trim() ? apiKey.trim() : undefined
        });
        setProviderStatus(saved);
        setApiKey("");
        await refreshAll(selectedProviderId);
        setNotice({
          title: "配置已保存",
          message: saved.message || "LLM Provider 配置已写入服务端。",
          tone: "success"
        });
      } catch (submitError) {
        setError(submitError instanceof Error ? submitError.message : "保存 LLM 配置失败。");
      }
    });
  }

  function handleActivate() {
    if (!selectedProviderId) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const activated = await activateLlmProvider(selectedProviderId);
        await refreshAll(selectedProviderId);
        setNotice({
          title: "Provider 已生效",
          message: activated.message || "当前 LLM 建议将使用此 Provider。",
          tone: "success"
        });
      } catch (activateError) {
        setError(activateError instanceof Error ? activateError.message : "切换 Provider 失败。");
      }
    });
  }

  function handleTest() {
    if (!selectedProviderId) {
      return;
    }

    setError("");
    setTestResult(null);
    startTransition(async () => {
      try {
        const { data } = await testLlmProvider(selectedProviderId, {
          authType,
          baseUrl,
          model,
          apiKey: apiKey.trim() ? apiKey.trim() : undefined
        });
        setTestResult(data);
        setNotice({
          title: data.ok ? "链路测试成功" : "链路测试失败",
          message: data.message,
          tone: data.ok ? "success" : "error"
        });
      } catch (testError) {
        setError(testError instanceof Error ? testError.message : "LLM 链路测试失败。");
      }
    });
  }

  function handleTestActive() {
    setError("");
    setTestResult(null);
    startTransition(async () => {
      try {
        const { data } = await testActiveLlmProvider();
        setTestResult(data);
        setNotice({
          title: data.ok ? "当前 Provider 连通" : "当前 Provider 异常",
          message: data.message,
          tone: data.ok ? "success" : "error"
        });
      } catch (testError) {
        setError(testError instanceof Error ? testError.message : "LLM 链路测试失败。");
      }
    });
  }

  async function pollSubscriptionOAuth(providerId: string, state: string) {
    const deadline = Date.now() + 120_000;
    while (Date.now() < deadline) {
      const result = await pollLlmSubscriptionOAuth(providerId, state);
      if (result.status === "complete" && result.configured) {
        return result;
      }
      if (result.status === "error") {
        throw new Error(result.message || "订阅登录失败。");
      }
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    throw new Error("订阅登录超时，请重试。");
  }

  function handleStartOAuth() {
    if (!selectedProviderId) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        await saveLlmProviderConfig(selectedProviderId, {
          authType,
          baseUrl,
          model
        });
        if (authType === "codex_oauth" || authType === "gemini_subscription") {
          const start = await startLlmSubscriptionOAuth(selectedProviderId, authType);
          if (!start.authorizationUrl) {
            throw new Error("未获取到订阅登录授权地址。");
          }
          window.open(start.authorizationUrl, "_blank", "noopener,noreferrer");
          if (start.requiresPoll) {
            await pollSubscriptionOAuth(selectedProviderId, start.state);
            await refreshAll(selectedProviderId);
            setNotice({
              title: "订阅登录成功",
              message: "账号已连接，可测试连接并设为生效。",
              tone: "success"
            });
          } else {
            window.location.assign(start.authorizationUrl);
          }
          return;
        }
        const start = await startLlmOAuth(selectedProviderId);
        if (!start.authorizationUrl) {
          throw new Error("未获取到 OAuth 授权地址。");
        }
        window.location.assign(start.authorizationUrl);
      } catch (oauthError) {
        setError(oauthError instanceof Error ? oauthError.message : "OAuth 连接失败。");
      }
    });
  }

  function handleRevokeOAuth() {
    if (!selectedProviderId) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const result =
          authType === "codex_oauth" || authType === "gemini_subscription"
            ? await revokeLlmSubscriptionOAuth(selectedProviderId, authType)
            : await revokeLlmOAuth(selectedProviderId);
        await refreshAll(selectedProviderId);
        setNotice({
          title: "连接已断开",
          message: result.message,
          tone: "warning"
        });
      } catch (revokeError) {
        setError(revokeError instanceof Error ? revokeError.message : "断开连接失败。");
      }
    });
  }

  const selectedProvider = providers.find((item) => item.providerId === selectedProviderId);
  const supportsCodexOAuth = Boolean(selectedProvider?.authTypes.includes("codex_oauth"));
  const showAuthTabs = supportsCodexOAuth;
  const resolvedModelOptions = modelOptions.length > 0 ? modelOptions : (selectedProvider?.models ?? []);
  const selectedModelOption = resolvedModelOptions.find((item) => item.modelId === model);
  const selectedModelSupportsVision = selectedModelOption?.supportsVision ?? false;
  const isActiveProvider = selectedProvider?.isActive ?? activeStatus?.providerId === selectedProviderId;
  const canActivate = Boolean(selectedProviderId && providerStatus?.configured && !isActiveProvider);
  const canTest = Boolean(
    selectedProviderId &&
      baseUrl.trim() &&
      model.trim() &&
      (isOAuthLikeAuthType(authType) ? providerStatus?.configured : apiKey.trim() || providerStatus?.configured)
  );
  const canTestActive = Boolean(activeStatus?.configured);

  return (
    <div className="space-y-6">
      <BlockingNotice
        description="正在加载或保存 LLM 配置，请稍候。"
        title="处理中"
        visible={loading || isPending}
      />
      <ToastNotice
        message={notice?.message ?? ""}
        title={notice?.title ?? ""}
        tone={notice?.tone}
        visible={Boolean(notice)}
      />

      <section className="surface-hero">
        <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Active Provider</p>
        <div className="mt-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-ink">
              {activeStatus?.providerName ?? "未加载"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-ink/70">
              在下方选择 Provider 并点击「设为生效」后，主题、分镜、导出等 LLM 建议会立即切换。
              若未在 UI 中指定，则回退到服务端环境变量 <code className="text-pine">LLM_PROVIDER</code>。
            </p>
          </div>
          {activeStatus ? (
            <span
              className={[
                "inline-flex rounded-full border px-4 py-2 text-sm font-medium",
                statusBadgeClass(activeStatus.status)
              ].join(" ")}
            >
              {STATUS_LABELS[activeStatus.status] ?? activeStatus.status}
            </span>
          ) : null}
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleTestActive}
            disabled={loading || isPending || !canTestActive}
            className="btn-secondary"
          >
            {isPending ? "测试中..." : "测试当前生效 Provider"}
          </button>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-3">
          <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Providers</p>
          {filterVisibleProviders(providers).map((provider) => {
            const selected = provider.providerId === selectedProviderId;
            return (
              <button
                key={provider.providerId}
                type="button"
                onClick={() => handleSelectProvider(provider.providerId)}
                disabled={loading || isPending}
                className={[
                  "w-full rounded-2xl border px-4 py-4 text-left transition disabled:cursor-not-allowed disabled:opacity-60",
                  selected
                    ? "border-pine/30 bg-sand/60 shadow-soft"
                    : "border-line bg-white hover:border-pine/20"
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-ink">{provider.providerName}</span>
                  {provider.isActive ? (
                    <span className="badge-ai">生效中</span>
                  ) : null}
                </div>
                <p className="mt-2 text-xs text-ink/60">
                  {PROVIDER_SUBTITLE_OVERRIDES[provider.providerId] ??
                    (provider.subtitle || provider.providerId)}
                </p>
                <p className="mt-2 text-xs text-ink/55">
                  {STATUS_LABELS[provider.status] ?? provider.status}
                </p>
              </button>
            );
          })}
        </aside>

        <section className="surface-panel p-6">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Connection</p>
              <h3 className="mt-2 text-2xl font-semibold text-ink">
                {selectedProvider?.providerName ?? "选择 Provider"}
              </h3>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                {authType === "codex_oauth"
                  ? "ChatGPT 登录 (Codex) 使用 ChatGPT Plus 订阅配额。授权时后端会在 localhost:1455 监听回调（实验性功能）。"
                  : authType === "gemini_subscription"
                    ? "Google 登录 (Gemini 订阅) 使用 Gemini CLI 同款 OAuth，走个人订阅/免费档配额（实验性功能）。"
                    : authType === "oauth"
                      ? "Platform OAuth 模式下由浏览器授权，Token 加密保存在后端。需自行配置 Client ID。"
                      : "API Key 仅保存在后端数据库，不会回显到浏览器。留空 API Key 字段则保留已有密钥不变。"}
              </p>
            </div>
            {providerStatus ? (
              <span
                className={[
                  "inline-flex rounded-full border px-4 py-2 text-sm font-medium",
                  statusBadgeClass(providerStatus.status)
                ].join(" ")}
              >
                {STATUS_LABELS[providerStatus.status] ?? providerStatus.status}
              </span>
            ) : null}
          </div>

          {!isActiveProvider ? (
            <div className="mt-4 rounded-2xl border border-amber-200/80 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
              此 Provider 尚未生效。保存配置或完成 OAuth 连接后，点击「设为生效」即可用于 LLM 建议。
            </div>
          ) : null}

          {showAuthTabs ? (
            <div className="mt-5 flex flex-wrap gap-2 rounded-full border border-line bg-white p-1">
              <button
                type="button"
                onClick={() => handleAuthTypeChange("api_key")}
                className={[
                  "rounded-full px-4 py-2 text-sm transition",
                  authType === "api_key" ? "bg-sand text-ink shadow-soft" : "text-ink/65"
                ].join(" ")}
              >
                API Key
              </button>
              {supportsCodexOAuth ? (
                <button
                  type="button"
                  onClick={() => handleAuthTypeChange("codex_oauth")}
                  className={[
                    "rounded-full px-4 py-2 text-sm transition",
                    authType === "codex_oauth" ? "bg-sand text-ink shadow-soft" : "text-ink/65"
                  ].join(" ")}
                >
                  ChatGPT 登录 (Codex)
                </button>
              ) : null}
            </div>
          ) : null}

          <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-sm text-ink/75">Base URL</span>
              <input
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="https://api.example.com/v1"
                className="input-field"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm text-ink/75">Model</span>
              {resolvedModelOptions.length > 0 && !useCustomModel ? (
                <select
                  value={
                    resolvedModelOptions.some((item) => item.modelId === model)
                      ? model
                      : resolvedModelOptions[0]?.modelId ?? model
                  }
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    if (nextValue === "__custom__") {
                      setUseCustomModel(true);
                      return;
                    }
                    setModel(nextValue);
                  }}
                  className="input-field"
                >
                  {resolvedModelOptions.map((option) => (
                    <option key={option.modelId} value={option.modelId}>
                      {option.label}
                      {option.recommended ? "（推荐）" : ""}
                      {option.supportsVision ? " · Vision" : ""}
                    </option>
                  ))}
                  <option value="__custom__">自定义 Model ID...</option>
                </select>
              ) : (
                <input
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder={selectedProvider?.defaultModel ?? "gpt-4.1-mini"}
                  className="input-field"
                />
              )}
              {resolvedModelOptions.length > 0 ? (
                <div className="mt-2 space-y-2 text-xs text-ink/60">
                  <span>
                    {selectedModelOption?.description ??
                      "可从官方模型列表选择，避免填错 Model ID。"}
                  </span>
                  {providerStatus?.configured ? (
                    <p className="text-ink/50">
                      {liveModelsMessage ||
                        (selectedModelOption?.visionSource === "live"
                          ? "模型 Vision 能力来自 Provider 实时列表。"
                          : selectedModelOption?.visionSource === "cache"
                            ? "模型 Vision 能力来自缓存的实时列表。"
                            : "模型 Vision 能力来自本地目录推断。")}
                    </p>
                  ) : null}
                  {!selectedModelSupportsVision && model.trim() ? (
                    <p className="rounded-xl border border-amber-200/80 bg-amber-50 px-3 py-2 text-amber-900">
                      当前模型不支持图像分析，素材「AI 分析」将无法使用。请切换到带 Vision
                      标记的模型（如 gpt-4o、gemini-2.0-flash、kimi-k2.5/k2.6）。
                    </p>
                  ) : null}
                  {useCustomModel ? (
                    <button
                      type="button"
                      onClick={() => {
                        setUseCustomModel(false);
                        setModel(recommendedModel(selectedProvider));
                      }}
                      className="text-pine underline-offset-2 hover:underline"
                    >
                      返回模型列表
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setUseCustomModel(true)}
                      className="text-pine underline-offset-2 hover:underline"
                    >
                      自定义 Model ID
                    </button>
                  )}
                </div>
              ) : null}
              {selectedProviderId === "kimi" && useCustomModel ? (
                <p className="mt-2 text-xs text-amber-800">
                  Kimi 官方 Model ID 形如 <code>kimi-k2.6</code>，不是 <code>k2.6</code>。
                </p>
              ) : null}
            </label>

            {isOAuthLikeAuthType(authType) ? (
              <div className="space-y-4 rounded-2xl border border-pine/15 bg-sand/40 p-4">
                <p className="text-sm leading-6 text-ink/75">
                  {providerStatus?.configured
                    ? "账号已连接。可重新授权覆盖，或断开后改回 API Key。"
                    : authType === "codex_oauth"
                      ? "点击连接后在新窗口完成 ChatGPT 登录，本页将自动等待授权结果。"
                      : authType === "gemini_subscription"
                        ? "点击连接后在新窗口完成 Google 登录，本页将自动等待授权结果。"
                        : "点击连接后跳转到厂商授权页，完成后会自动回到本系统。"}
                </p>
                {providerStatus?.status === "expired" ? (
                  <div className="rounded-xl border border-clay/15 bg-[#fff5ef] px-3 py-2 text-sm text-clay">
                    授权已过期，请重新连接。
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={handleStartOAuth}
                    disabled={loading || isPending}
                    className="btn-ai"
                  >
                    {providerStatus?.configured
                      ? authType === "codex_oauth"
                        ? "重新连接 ChatGPT"
                        : authType === "gemini_subscription"
                          ? "重新连接 Google"
                          : "重新连接 OAuth"
                      : authType === "codex_oauth"
                        ? "连接 ChatGPT 账号"
                        : authType === "gemini_subscription"
                          ? "连接 Google 账号"
                          : "连接 OAuth 账号"}
                  </button>
                  {providerStatus?.configured ? (
                    <button
                      type="button"
                      onClick={handleRevokeOAuth}
                      disabled={loading || isPending}
                      className="btn-secondary"
                    >
                      断开连接
                    </button>
                  ) : null}
                </div>
              </div>
            ) : (
              <label className="block">
                <span className="mb-2 block text-sm text-ink/75">API Key</span>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder={
                    providerStatus?.configured ? "已配置，输入新 Key 可覆盖" : "请输入 API Key"
                  }
                  autoComplete="off"
                  className="input-field"
                />
              </label>
            )}

            <div className="stat-cell">
              {selectedProviderId === "openai"
                ? "OpenAI 已合并原 OpenAI Compatible：可通过 Base URL 指向 Azure / 代理端点，无需单独 Provider。"
                : "若服务端 `.env` 中也配置了 "}
              {selectedProviderId !== "openai" ? (
                <>
                  <code className="text-pine">LLM_API_KEY</code>，数据库中的 Key 会优先生效。
                </>
              ) : null}
            </div>

            {error ? (
              <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay">
                {error}
              </div>
            ) : null}

            <div className="flex flex-wrap gap-3">
              <button
                type="submit"
                disabled={loading || isPending || !selectedProviderId}
                className="btn-primary"
              >
                {isPending ? "保存中..." : "保存配置"}
              </button>
              <button
                type="button"
                onClick={handleTest}
                disabled={loading || isPending || !canTest}
                className="btn-secondary"
              >
                {isPending ? "测试中..." : "测试连接"}
              </button>
              {!isActiveProvider ? (
                <button
                  type="button"
                  onClick={handleActivate}
                  disabled={loading || isPending || !canActivate}
                  className="btn-ai"
                >
                  {isPending ? "处理中..." : "设为生效"}
                </button>
              ) : (
                <span className="badge-ai px-4 py-2.5 text-sm">当前已生效</span>
              )}
            </div>

            {testResult ? (
              <div
                className={[
                  "rounded-2xl border px-4 py-4 text-sm leading-6",
                  testResult.ok
                    ? "border-pine/20 bg-mist text-ink/80"
                    : "border-clay/15 bg-[#fff5ef] text-clay"
                ].join(" ")}
              >
                <p className="font-medium text-ink">
                  {testResult.ok ? "测试结果：连通" : "测试结果：失败"}
                  {testResult.latencyMs > 0 ? `（${testResult.latencyMs}ms）` : ""}
                </p>
                <p className="mt-2">{testResult.message}</p>
                <p className="mt-2 break-all text-xs text-ink/60">
                  Endpoint: {testResult.endpointUrl}
                </p>
                <p className="mt-1 text-xs text-ink/60">
                  Model: {testResult.model} · Provider: {testResult.providerName}
                </p>
                {testResult.replyPreview ? (
                  <p className="mt-2 text-xs text-ink/70">Reply: {testResult.replyPreview}</p>
                ) : null}
              </div>
            ) : null}
          </form>
        </section>
      </div>

      <LlmAuditSection logs={auditLogs} />
    </div>
  );
}
