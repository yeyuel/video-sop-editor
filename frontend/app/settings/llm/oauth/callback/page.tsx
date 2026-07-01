"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, useTransition } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import {
  completeLlmOAuthCallback,
  completeLlmSubscriptionOAuthCallback
} from "@/lib/browser-api";

export default function LlmOAuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const code = searchParams.get("code") ?? "";
    const state = searchParams.get("state") ?? "";
    const providerId = searchParams.get("provider") ?? "openai";
    const authType = searchParams.get("authType") ?? "";

    if (!code || !state) {
      setError("OAuth 回调缺少 code 或 state 参数。");
      return;
    }

    startTransition(async () => {
      try {
        const status =
          authType === "codex_oauth" || authType === "gemini_subscription"
            ? await completeLlmSubscriptionOAuthCallback(
                providerId,
                authType,
                { code, state }
              )
            : await completeLlmOAuthCallback(providerId, { code, state });
        setNotice(status.message || "OAuth 授权成功。");
        window.setTimeout(() => {
          router.replace("/settings/llm?oauth=success");
        }, 1200);
      } catch (callbackError) {
        setError(
          callbackError instanceof Error ? callbackError.message : "OAuth 回调处理失败。"
        );
      }
    });
  }, [router, searchParams]);

  return (
    <div className="mx-auto max-w-lg space-y-4 py-16">
      <BlockingNotice visible={isPending} title="正在完成 OAuth 授权" description="请稍候…" />
      <ToastNotice visible={Boolean(notice)} title="授权成功" message={notice} tone="success" />
      <div className="surface-panel p-6">
        <h1 className="text-xl font-semibold text-ink">LLM OAuth 回调</h1>
        {error ? (
          <>
            <p className="mt-3 text-sm leading-6 text-clay">{error}</p>
            <Link href="/settings/llm" className="btn-secondary mt-5 inline-flex">
              返回 LLM 设置
            </Link>
          </>
        ) : (
          <p className="mt-3 text-sm leading-6 text-ink/70">
            {isPending ? "正在验证授权并保存 Token…" : "即将返回 LLM 设置页。"}
          </p>
        )}
      </div>
    </div>
  );
}
