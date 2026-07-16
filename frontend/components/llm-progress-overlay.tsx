"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

import {
  formatElapsed,
  stageStatus,
  type LlmProgressViewState
} from "@/lib/llm-progress-stages";
import { cancelActiveLlmTask } from "@/lib/llm-stream";

type LlmProgressOverlayProps = {
  state: LlmProgressViewState;
  visible: boolean;
};

export function LlmProgressOverlay({ state, visible }: LlmProgressOverlayProps) {
  const [elapsedSec, setElapsedSec] = useState(0);
  const [isCancelling, setIsCancelling] = useState(false);

  useEffect(() => {
    if (!visible) {
      return;
    }

    setElapsedSec(Math.floor((Date.now() - state.startedAt) / 1000));
    const timer = window.setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - state.startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [state.startedAt, visible]);

  if (!visible) {
    return null;
  }

  async function handleCancel() {
    setIsCancelling(true);
    try {
      const requested = await cancelActiveLlmTask();
      if (!requested) setIsCancelling(false);
    } catch {
      setIsCancelling(false);
    }
  }

  const progress = Math.max(0, Math.min(state.progress, 100));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/25 px-6 backdrop-blur-sm">
      <div className="surface-panel w-full max-w-lg border-ai/15 p-6 shadow-ai">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="badge-ai">LLM 生成中</p>
            <h3 className="mt-2 text-xl font-semibold text-ink">{state.title}</h3>
          </div>
          <div className="stat-pill">已用时 {formatElapsed(elapsedSec)}</div>
        </div>

        <p className="mt-4 text-sm leading-6 text-ink/80">{state.message}</p>
        {state.detail ? (
          <p className="mt-1 text-xs leading-5 text-ink/55">{state.detail}</p>
        ) : null}

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-sand">
          <div
            className="h-full rounded-full bg-ai transition-all duration-500 ease-out"
            style={{ width: `${Math.max(progress, 8)}%` }}
          />
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-ink/50">
          <span>阶段进度（非精确百分比）</span>
          <span>{progress > 0 ? `${progress}%` : "启动中"}</span>
        </div>

        <ol className="mt-5 space-y-2">
          {state.stages.map((stage) => {
            const status = stageStatus(state.stages, stage.id, state.currentStage);
            return (
              <li
                key={stage.id}
                className={clsx(
                  "flex items-center gap-3 rounded-2xl px-3 py-2 text-sm transition",
                  status === "active" && "bg-ai-soft text-ink",
                  status === "done" && "text-ink/70",
                  status === "pending" && "text-ink/45"
                )}
              >
                <span
                  className={clsx(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    status === "active" && "bg-ai text-white",
                    status === "done" && "bg-pine/15 text-pine",
                    status === "pending" && "bg-black/5 text-ink/35"
                  )}
                >
                  {status === "done" ? "✓" : status === "active" ? "•" : ""}
                </span>
                <span className={clsx(status === "active" && "font-medium")}>{stage.label}</span>
              </li>
            );
          })}
        </ol>

        <p className="mt-5 text-center text-xs leading-5 text-ink/50">
          请保持页面打开。模型响应较慢时会每 5 秒更新等待状态。
        </p>
        <div className="mt-4 flex justify-center">
          <button
            type="button"
            className="btn-secondary px-5 py-2 text-sm"
            disabled={isCancelling}
            onClick={handleCancel}
          >
            {isCancelling ? "正在取消..." : "取消生成"}
          </button>
        </div>
      </div>
    </div>
  );
}
