import type { LlmMeta } from "@/lib/llm-status";
import { getBrowserApiBaseUrl, readApiErrorDetail } from "@/lib/api-base";

export type LlmStreamResult<T> = {
  data: T;
  meta?: LlmMeta;
};

export type LlmStreamTaskEvent = {
  type: "task";
  taskId: string;
  status: string;
  operation: string;
};

export type LlmStreamProgressEvent = {
  type: "progress";
  taskId?: string;
  stage: string;
  message: string;
  progress?: number;
  detail?: string;
};

export type LlmStreamCompleteEvent<T> = {
  type: "complete";
  taskId?: string;
  stage: string;
  message: string;
  progress: number;
  data: T;
  meta?: LlmMeta;
};

export type LlmStreamErrorEvent = {
  type: "error";
  taskId?: string;
  status?: string;
  message: string;
};

export type LlmStreamEvent<T> =
  | LlmStreamTaskEvent
  | LlmStreamProgressEvent
  | LlmStreamCompleteEvent<T>
  | LlmStreamErrorEvent;

type LlmTaskSnapshot<T> = {
  taskId: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled" | "interrupted";
  stage: string;
  message: string;
  detail: string;
  progress: number;
  data: T | null;
  meta?: LlmMeta;
  errorMessage: string;
};

let activeTaskId = "";
const ACTIVE_TASK_STORAGE_KEY = "video-sop-editor:active-llm-task";
const RETRYABLE_REQUEST_STORAGE_KEY = "video-sop-editor:retryable-llm-request";
export const LLM_RETRYABLE_REQUEST_EVENT = "video-sop-editor:llm-retryable-request";

export type StoredLlmTask = {
  taskId: string;
  operation: string;
  pagePath: string;
};

export type RetryableLlmRequest = {
  body: unknown;
  failedAt: string;
  message: string;
  pagePath: string;
  path: string;
  reconnectRequired?: boolean;
};

function notifyRetryableRequestChanged() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(LLM_RETRYABLE_REQUEST_EVENT));
  }
}

function storeRetryableRequest(
  path: string,
  body: unknown,
  error: unknown,
  reconnectRequired = false
) {
  if (typeof window === "undefined") return;
  const request: RetryableLlmRequest = {
    body,
    failedAt: new Date().toISOString(),
    message: error instanceof Error ? error.message : "生成任务失败。",
    pagePath: window.location.pathname,
    path,
    reconnectRequired
  };
  window.localStorage.setItem(RETRYABLE_REQUEST_STORAGE_KEY, JSON.stringify(request));
  notifyRetryableRequestChanged();
}

export function getRetryableLlmRequest(): RetryableLlmRequest | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(RETRYABLE_REQUEST_STORAGE_KEY);
  if (!raw) return null;
  try {
    const request = JSON.parse(raw) as RetryableLlmRequest;
    if (!request.path || request.pagePath !== window.location.pathname) return null;
    return request;
  } catch {
    window.localStorage.removeItem(RETRYABLE_REQUEST_STORAGE_KEY);
    return null;
  }
}

export function clearRetryableLlmRequest() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(RETRYABLE_REQUEST_STORAGE_KEY);
  notifyRetryableRequestChanged();
}

function storeActiveTask(event: LlmStreamTaskEvent) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    ACTIVE_TASK_STORAGE_KEY,
    JSON.stringify({
      taskId: event.taskId,
      operation: event.operation,
      pagePath: window.location.pathname
    } satisfies StoredLlmTask)
  );
}

function clearStoredTask(taskId?: string) {
  if (typeof window === "undefined") return;
  const stored = getStoredLlmTask();
  if (!taskId || !stored || stored.taskId === taskId) {
    window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
  }
}

export function getStoredLlmTask(): StoredLlmTask | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(ACTIVE_TASK_STORAGE_KEY);
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as StoredLlmTask;
    if (!value.taskId || value.pagePath !== window.location.pathname) return null;
    return value;
  } catch {
    window.localStorage.removeItem(ACTIVE_TASK_STORAGE_KEY);
    return null;
  }
}

export async function cancelActiveLlmTask(): Promise<boolean> {
  if (!activeTaskId) activeTaskId = getStoredLlmTask()?.taskId ?? "";
  if (!activeTaskId) {
    return false;
  }
  const response = await fetch(`${getBrowserApiBaseUrl()}/llm/tasks/${activeTaskId}/cancel`, {
    method: "POST",
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }
  return true;
}

async function getTaskSnapshot<T>(taskId: string): Promise<LlmTaskSnapshot<T>> {
  const response = await fetch(`${getBrowserApiBaseUrl()}/llm/tasks/${taskId}`, {
    credentials: "include",
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }
  const payload = (await response.json()) as { data: LlmTaskSnapshot<T> };
  return payload.data;
}

async function recoverTaskByPolling<T>(
  taskId: string,
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  while (true) {
    if (signal?.aborted) {
      await cancelActiveLlmTask().catch(() => false);
      throw new DOMException("任务已取消。", "AbortError");
    }

    const snapshot = await getTaskSnapshot<T>(taskId);
    if (snapshot.status === "completed" && snapshot.data !== null) {
      const event: LlmStreamCompleteEvent<T> = {
        type: "complete",
        taskId,
        stage: "complete",
        message: snapshot.message || "生成完成",
        progress: 100,
        data: snapshot.data,
        meta: snapshot.meta
      };
      onEvent(event);
      activeTaskId = "";
      clearStoredTask(taskId);
      return { data: snapshot.data, meta: snapshot.meta };
    }
    if (["failed", "cancelled", "interrupted"].includes(snapshot.status)) {
      activeTaskId = "";
      clearStoredTask(taskId);
      throw new Error(snapshot.errorMessage || snapshot.message || "生成任务未完成。");
    }

    onEvent({
      type: "progress",
      taskId,
      stage: snapshot.stage,
      message: snapshot.message || "后台任务仍在执行。",
      detail: snapshot.detail,
      progress: snapshot.progress
    });
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
  }
}

async function consumeStream<T>(
  response: Response,
  onEvent: (event: LlmStreamEvent<T>) => void
): Promise<LlmStreamResult<T> | null> {
  if (!response.body) {
    throw new Error("当前环境不支持流式响应，请刷新后重试。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let complete: LlmStreamResult<T> | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((item) => item.trim())
        .find((item) => item.startsWith("data: "));
      if (!line) continue;
      const event = JSON.parse(line.slice(6)) as LlmStreamEvent<T>;
      if (event.type === "task") {
        activeTaskId = event.taskId;
        storeActiveTask(event);
      }
      onEvent(event);
      if (event.type === "complete") {
        complete = { data: event.data, meta: event.meta };
        clearStoredTask(event.taskId);
      }
      if (event.type === "error") {
        clearStoredTask(event.taskId);
        activeTaskId = "";
        throw new Error(event.message);
      }
    }
  }
  if (complete) activeTaskId = "";
  return complete;
}

export function recoverStoredLlmTask<T>(
  onEvent: (event: LlmStreamEvent<T>) => void
): Promise<LlmStreamResult<T>> | null {
  const stored = getStoredLlmTask();
  if (!stored) return null;
  activeTaskId = stored.taskId;
  return recoverTaskByPolling<T>(stored.taskId, onEvent);
}

async function runRecoverableStream<T>(
  responsePromise: Promise<Response>,
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  try {
    const response = await responsePromise;
    if (!response.ok) throw new Error(await readApiErrorDetail(response));
    const result = await consumeStream(response, onEvent);
    if (result) return result;
  } catch (error) {
    if (signal?.aborted) {
      await cancelActiveLlmTask().catch(() => false);
      activeTaskId = "";
      throw error;
    }
    if (!activeTaskId) throw error;
  }

  if (!activeTaskId) throw new Error("生成任务未正常启动，请稍后重试。");
  return recoverTaskByPolling(activeTaskId, onEvent, signal);
}

export function postLlmStream<T>(
  path: string,
  body: unknown,
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  activeTaskId = "";
  return runRecoverableStream(
    fetch(`${getBrowserApiBaseUrl()}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(body),
      signal
    }),
    onEvent,
    signal
  )
    .then((result) => {
      const reconnectRequired = ["auth_invalid", "not_configured"].includes(
        result.meta?.llmErrorCode ?? ""
      );
      if (reconnectRequired) {
        storeRetryableRequest(
          path,
          body,
          new Error(result.meta?.llmMessage || "LLM 连接已失效，请重新连接后重试。"),
          true
        );
      } else {
        clearRetryableLlmRequest();
      }
      return result;
    })
    .catch((error) => {
      const errorMessage = error instanceof Error ? error.message : "";
      if (
        !signal?.aborted &&
        !(error instanceof DOMException && error.name === "AbortError") &&
        !errorMessage.includes("取消")
      ) {
        storeRetryableRequest(path, body, error);
      }
      throw error;
    });
}

export function retryLastFailedLlmRequest<T>(
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  const request = getRetryableLlmRequest();
  if (!request) {
    return Promise.reject(new Error("没有可重试的生成任务。"));
  }
  return postLlmStream<T>(request.path, request.body, onEvent, signal);
}

export function postLlmStreamFormData<T>(
  path: string,
  formData: FormData,
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  activeTaskId = "";
  return runRecoverableStream(
    fetch(`${getBrowserApiBaseUrl()}${path}`, {
      method: "POST",
      credentials: "include",
      headers: { Accept: "text/event-stream" },
      body: formData,
      signal
    }),
    onEvent,
    signal
  );
}
