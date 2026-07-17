"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  clearRetryableLlmRequest,
  getRetryableLlmRequest,
  LLM_RETRYABLE_REQUEST_EVENT,
  retryLastFailedLlmRequest,
  type RetryableLlmRequest
} from "@/lib/llm-stream";

export function LlmRetryBanner() {
  const [request, setRequest] = useState<RetryableLlmRequest | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryMessage, setRetryMessage] = useState("");

  useEffect(() => {
    const refresh = () => setRequest(getRetryableLlmRequest());
    refresh();
    window.addEventListener(LLM_RETRYABLE_REQUEST_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(LLM_RETRYABLE_REQUEST_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  if (!request) return null;

  async function handleRetry() {
    setIsRetrying(true);
    setRetryMessage("正在使用原参数重新生成…");
    try {
      await retryLastFailedLlmRequest((event) => {
        if (event.type === "progress") {
          setRetryMessage(event.message || "正在重新生成…");
        }
      });
      clearRetryableLlmRequest();
      window.location.reload();
    } catch (error) {
      setRetryMessage(error instanceof Error ? error.message : "重试失败，请稍后再试。");
      setIsRetrying(false);
    }
  }

  return (
    <aside className="fixed inset-x-4 bottom-5 z-[70] mx-auto max-w-3xl rounded-3xl border border-clay/20 bg-white/95 p-4 shadow-card backdrop-blur md:px-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <p className="font-semibold text-ink">
            {request.reconnectRequired ? "LLM 连接已失效，生成上下文已保留" : "上一次生成没有完成"}
          </p>
          <p className="mt-1 truncate text-sm text-ink/60">
            {retryMessage || request.message || "可以使用原来的配置重新尝试。"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {request.reconnectRequired ? (
            <Link href="/settings/llm" className="btn-secondary px-4 py-2">
              重新连接
            </Link>
          ) : null}
          <button
            type="button"
            onClick={handleRetry}
            disabled={isRetrying}
            className="btn-primary px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isRetrying ? "重试中…" : "原参数重试"}
          </button>
          <button
            type="button"
            onClick={clearRetryableLlmRequest}
            disabled={isRetrying}
            className="btn-ghost px-3 py-2"
          >
            忽略
          </button>
        </div>
      </div>
    </aside>
  );
}
