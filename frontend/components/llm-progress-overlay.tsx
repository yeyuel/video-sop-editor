"use client";

import clsx from "clsx";
import { useEffect, useState } from "react";

import {
  formatElapsed,
  stageStatus,
  type LlmProgressViewState
} from "@/lib/llm-progress-stages";

type LlmProgressOverlayProps = {
  state: LlmProgressViewState;
  visible: boolean;
};

export function LlmProgressOverlay({ state, visible }: LlmProgressOverlayProps) {
  const [elapsedSec, setElapsedSec] = useState(0);

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

  const progress = Math.max(0, Math.min(state.progress, 100));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/25 px-6 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-[28px] border border-white/70 bg-white/95 p-6 shadow-[0_28px_80px_rgba(25,34,41,0.16)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-pine/70">
              LLM 生成中
            </p>
            <h3 className="mt-1 text-xl font-semibold text-ink">{state.title}</h3>
          </div>
          <div className="rounded-full bg-mist px-3 py-1 text-xs font-medium text-pine">
            已用时 {formatElapsed(elapsedSec)}
          </div>
        </div>

        <p className="mt-4 text-sm leading-6 text-ink/80">{state.message}</p>
        {state.detail ? (
          <p className="mt-1 text-xs leading-5 text-ink/55">{state.detail}</p>
        ) : null}

        <div className="mt-5 h-2 overflow-hidden rounded-full bg-mist">
          <div
            className="h-full rounded-full bg-pine transition-all duration-500 ease-out"
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
                  status === "active" && "bg-mist text-ink",
                  status === "done" && "text-ink/70",
                  status === "pending" && "text-ink/45"
                )}
              >
                <span
                  className={clsx(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                    status === "active" && "bg-pine text-white",
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
      </div>
    </div>
  );
}
