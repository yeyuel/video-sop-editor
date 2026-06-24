"use client";

import { useCallback, useState } from "react";

import {
  applyLlmProgressEvent,
  createLlmProgressState,
  type LlmProgressViewState,
  type LlmStageDefinition
} from "@/lib/llm-progress-stages";
import type { LlmStreamProgressEvent } from "@/lib/llm-stream";

export function useLlmProgress() {
  const [llmProgress, setLlmProgress] = useState<LlmProgressViewState | null>(null);

  const start = useCallback((title: string, stages: LlmStageDefinition[]) => {
    const next = createLlmProgressState(title, stages);
    setLlmProgress(next);
    return next;
  }, []);

  const onProgress = useCallback((event: LlmStreamProgressEvent) => {
    setLlmProgress((current) => (current ? applyLlmProgressEvent(current, event) : current));
  }, []);

  const finish = useCallback(() => {
    setLlmProgress(null);
  }, []);

  return {
    llmProgress,
    isLlmRunning: Boolean(llmProgress),
    start,
    onProgress,
    finish
  };
}
