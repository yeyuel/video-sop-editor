"use client";

import { useCallback, useEffect, useState } from "react";

import {
  applyLlmProgressEvent,
  createLlmProgressState,
  type LlmProgressViewState,
  type LlmStageDefinition
} from "@/lib/llm-progress-stages";
import type { LlmStreamProgressEvent } from "@/lib/llm-stream";
import { getStoredLlmTask, recoverStoredLlmTask } from "@/lib/llm-stream";

const PROGRESS_STORAGE_KEY = "video-sop-editor:llm-progress-view";

export function useLlmProgress() {
  const [llmProgress, setLlmProgress] = useState<LlmProgressViewState | null>(null);

  const start = useCallback((title: string, stages: LlmStageDefinition[]) => {
    const next = createLlmProgressState(title, stages);
    setLlmProgress(next);
    window.sessionStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify(next));
    return next;
  }, []);

  const onProgress = useCallback((event: LlmStreamProgressEvent) => {
    setLlmProgress((current) => {
      if (!current) return current;
      const next = applyLlmProgressEvent(current, event);
      window.sessionStorage.setItem(PROGRESS_STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const finish = useCallback(() => {
    setLlmProgress(null);
    window.sessionStorage.removeItem(PROGRESS_STORAGE_KEY);
  }, []);

  useEffect(() => {
    if (!getStoredLlmTask()) return;
    let restored = createLlmProgressState("正在恢复生成任务", [
      { id: "queued", label: "恢复任务连接" },
      { id: "calling_llm", label: "模型继续生成" },
      { id: "parsing", label: "解析生成结果" },
      { id: "saving", label: "保存业务数据" },
      { id: "complete", label: "生成完成" }
    ]);
    const storedView = window.sessionStorage.getItem(PROGRESS_STORAGE_KEY);
    if (storedView) {
      try {
        restored = JSON.parse(storedView) as LlmProgressViewState;
      } catch {
        window.sessionStorage.removeItem(PROGRESS_STORAGE_KEY);
      }
    }
    setLlmProgress(restored);

    const recovery = recoverStoredLlmTask((event) => {
      if (event.type !== "progress") return;
      setLlmProgress((current) =>
        current ? applyLlmProgressEvent(current, event) : current
      );
    });
    recovery
      ?.then(() => {
        window.sessionStorage.removeItem(PROGRESS_STORAGE_KEY);
        window.location.reload();
      })
      .catch(() => {
        window.sessionStorage.removeItem(PROGRESS_STORAGE_KEY);
        setLlmProgress(null);
      });
  }, []);

  return {
    llmProgress,
    isLlmRunning: Boolean(llmProgress),
    start,
    onProgress,
    finish
  };
}
