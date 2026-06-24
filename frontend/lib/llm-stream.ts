import type { LlmMeta } from "@/lib/llm-status";
import { getBrowserApiBaseUrl, readApiErrorDetail } from "@/lib/api-base";

export type LlmStreamResult<T> = {
  data: T;
  meta?: LlmMeta;
};

export type LlmStreamProgressEvent = {
  type: "progress";
  stage: string;
  message: string;
  progress?: number;
  detail?: string;
};

export type LlmStreamCompleteEvent<T> = {
  type: "complete";
  stage: string;
  message: string;
  progress: number;
  data: T;
  meta?: LlmMeta;
};

export type LlmStreamErrorEvent = {
  type: "error";
  message: string;
};

export type LlmStreamEvent<T> =
  | LlmStreamProgressEvent
  | LlmStreamCompleteEvent<T>
  | LlmStreamErrorEvent;

export async function postLlmStream<T>(
  path: string,
  body: unknown,
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  const response = await fetch(`${getBrowserApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream"
    },
    body: JSON.stringify(body),
    signal
  });

  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }

  if (!response.body) {
    throw new Error("当前环境不支持流式响应，请刷新后重试。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let complete: LlmStreamResult<T> | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((item) => item.trim())
        .find((item) => item.startsWith("data: "));
      if (!line) {
        continue;
      }

      const event = JSON.parse(line.slice(6)) as LlmStreamEvent<T>;
      onEvent(event);

      if (event.type === "complete") {
        complete = { data: event.data, meta: event.meta };
      }
      if (event.type === "error") {
        throw new Error(event.message);
      }
    }
  }

  if (!complete) {
    throw new Error("LLM 生成未完成，请稍后重试。");
  }

  return complete;
}

export async function postLlmStreamFormData<T>(
  path: string,
  formData: FormData,
  onEvent: (event: LlmStreamEvent<T>) => void,
  signal?: AbortSignal
): Promise<LlmStreamResult<T>> {
  const response = await fetch(`${getBrowserApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream"
    },
    body: formData,
    signal
  });

  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }

  if (!response.body) {
    throw new Error("当前环境不支持流式响应，请刷新后重试。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let complete: LlmStreamResult<T> | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk
        .split("\n")
        .map((item) => item.trim())
        .find((item) => item.startsWith("data: "));
      if (!line) {
        continue;
      }

      const event = JSON.parse(line.slice(6)) as LlmStreamEvent<T>;
      onEvent(event);

      if (event.type === "complete") {
        complete = { data: event.data, meta: event.meta };
      }
      if (event.type === "error") {
        throw new Error(event.message);
      }
    }
  }

  if (!complete) {
    throw new Error("处理未完成，请稍后重试。");
  }

  return complete;
}
