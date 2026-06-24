"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useState, useTransition } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import {
  activateLlmProvider,
  getLlmProviderStatus,
  getLlmProviders,
  getLlmStatus,
  saveLlmProviderConfig,
  testActiveLlmProvider,
  testLlmProvider
} from "@/lib/browser-api";
import type { LlmProvider, LlmStatus, LlmTestResult } from "@/lib/llm-status";

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

function recommendedModel(provider?: LlmProvider | null) {
  if (!provider) {
    return "";
  }
  return provider.models.find((item) => item.recommended)?.modelId ?? provider.defaultModel;
}

function isKnownModel(modelId: string, provider?: LlmProvider | null) {
  if (!modelId.trim()) {
    return false;
  }
  return Boolean(provider?.models.some((item) => item.modelId === modelId));
}

export function LlmSettingsClient() {
  const [providers, setProviders] = useState<LlmProvider[]>([]);
  const [activeStatus, setActiveStatus] = useState<LlmStatus | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState("");
  const [providerStatus, setProviderStatus] = useState<LlmStatus | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success";
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [isPending, startTransition] = useTransition();
  const [testResult, setTestResult] = useState<LlmTestResult | null>(null);
  const [useCustomModel, setUseCustomModel] = useState(false);

  const loadProviderForm = useCallback(async (providerId: string, providerList: LlmProvider[]) => {
    const status = await getLlmProviderStatus(providerId);
    const provider = providerList.find((item) => item.providerId === providerId);
    const nextModel = status.model || recommendedModel(provider);
    setProviderStatus(status);
    setBaseUrl(status.baseUrl);
    setUseCustomModel(!isKnownModel(nextModel, provider));
    setModel(nextModel);
    setApiKey("");
  }, []);

  const refreshAll = useCallback(
    async (providerId?: string) => {
      const [providerList, active] = await Promise.all([getLlmProviders(), getLlmStatus()]);
      setProviders(providerList);
      setActiveStatus(active);
      const targetId =
        providerId ??
        providerList.find((item) => item.isActive)?.providerId ??
        active.providerId ??
        "";
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
        const [providerList, active] = await Promise.all([getLlmProviders(), getLlmStatus()]);
        if (cancelled) {
          return;
        }
        setProviders(providerList);
        setActiveStatus(active);
        const initialId =
          providerList.find((item) => item.isActive)?.providerId ??
          active.providerId ??
          providerList[0]?.providerId ??
          "";
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
    if (!notice) {
      return;
    }
    const timer = window.setTimeout(() => setNotice(null), 2800);
    return () => window.clearTimeout(timer);
  }, [notice]);

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

  const selectedProvider = providers.find((item) => item.providerId === selectedProviderId);
  const modelOptions = selectedProvider?.models ?? [];
  const isActiveProvider = selectedProvider?.isActive ?? activeStatus?.providerId === selectedProviderId;
  const canActivate = Boolean(selectedProviderId && providerStatus?.configured && !isActiveProvider);
  const canTest = Boolean(
    selectedProviderId && baseUrl.trim() && model.trim() && (apiKey.trim() || providerStatus?.configured)
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

      <section className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card">
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
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "测试中..." : "测试当前生效 Provider"}
          </button>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-3">
          <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Providers</p>
          {providers.map((provider) => {
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
                    ? "border-pine bg-mist shadow-card"
                    : "border-black/5 bg-white/85 hover:border-pine/20"
                ].join(" ")}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium text-ink">{provider.providerName}</span>
                  {provider.isActive ? (
                    <span className="rounded-full bg-white px-2 py-1 text-xs text-pine">生效中</span>
                  ) : null}
                </div>
                <p className="mt-2 text-xs text-ink/60">{provider.providerId}</p>
                <p className="mt-2 text-xs text-ink/55">
                  {STATUS_LABELS[provider.status] ?? provider.status}
                </p>
              </button>
            );
          })}
        </aside>

        <section className="rounded-xl2 border border-black/5 bg-white/85 p-6 shadow-card">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-pine/70">API Key Config</p>
              <h3 className="mt-2 text-2xl font-semibold text-ink">
                {selectedProvider?.providerName ?? "选择 Provider"}
              </h3>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                API Key 仅保存在后端数据库，不会回显到浏览器。留空 API Key 字段则保留已有密钥不变。
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
              此 Provider 尚未生效。保存 API Key 后，点击「设为生效」即可用于 LLM 建议。
            </div>
          ) : null}

          <form className="mt-6 space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-sm text-ink/75">Base URL</span>
              <input
                value={baseUrl}
                onChange={(event) => setBaseUrl(event.target.value)}
                placeholder="https://api.example.com/v1"
                className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-sm text-ink/75">Model</span>
              {modelOptions.length > 0 && !useCustomModel ? (
                <select
                  value={modelOptions.some((item) => item.modelId === model) ? model : modelOptions[0]?.modelId ?? model}
                  onChange={(event) => {
                    const nextValue = event.target.value;
                    if (nextValue === "__custom__") {
                      setUseCustomModel(true);
                      return;
                    }
                    setModel(nextValue);
                  }}
                  className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
                >
                  {modelOptions.map((option) => (
                    <option key={option.modelId} value={option.modelId}>
                      {option.label}
                      {option.recommended ? "（推荐）" : ""}
                    </option>
                  ))}
                  <option value="__custom__">自定义 Model ID...</option>
                </select>
              ) : (
                <input
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  placeholder={selectedProvider?.defaultModel ?? "gpt-4.1-mini"}
                  className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
                />
              )}
              {modelOptions.length > 0 ? (
                <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-ink/60">
                  <span>
                    {modelOptions.find((item) => item.modelId === model)?.description ??
                      "可从官方模型列表选择，避免填错 Model ID。"}
                  </span>
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
                className="w-full rounded-2xl border border-pine/20 bg-white px-4 py-3 text-base text-ink outline-none transition focus:border-pine"
              />
            </label>

            <div className="rounded-2xl border border-pine/10 bg-sand/50 px-4 py-3 text-sm leading-6 text-ink/70">
              默认地址与模型可在上方修改。若服务端 `.env` 中也配置了{" "}
              <code className="text-pine">LLM_API_KEY</code>，数据库中的 Key 会优先生效。
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
                className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "保存中..." : "保存配置"}
              </button>
              <button
                type="button"
                onClick={handleTest}
                disabled={loading || isPending || !canTest}
                className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "测试中..." : "测试连接"}
              </button>
              {!isActiveProvider ? (
                <button
                  type="button"
                  onClick={handleActivate}
                  disabled={loading || isPending || !canActivate}
                  className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isPending ? "处理中..." : "设为生效"}
                </button>
              ) : (
                <span className="inline-flex items-center rounded-full border border-pine/20 bg-mist px-5 py-3 text-sm font-medium text-pine">
                  当前已生效
                </span>
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
    </div>
  );
}
