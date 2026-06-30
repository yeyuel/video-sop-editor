export type LlmMeta = {
  llmStatus?: string;
  llmMessage?: string;
  llmProviderId?: string;
  llmUsedFallback?: string;
  storyboardCaptionsUpdated?: string;
};

export type ApiEnvelopeWithMeta<T> = {
  success: boolean;
  data: T;
  meta?: LlmMeta & Record<string, string>;
};

export type LlmModelOption = {
  modelId: string;
  label: string;
  description: string;
  recommended: boolean;
  supportsVision?: boolean;
  visionSource?: string;
};

export type LlmProvider = {
  providerId: string;
  providerName: string;
  authTypes: string[];
  defaultBaseUrl: string;
  defaultModel: string;
  openaiCompatible: boolean;
  status: string;
  isActive: boolean;
  models: LlmModelOption[];
};

export type LlmStatus = {
  providerId: string;
  providerName: string;
  authType: string;
  status: string;
  baseUrl: string;
  model: string;
  configured: boolean;
  message: string;
};

export type LlmTestResult = {
  ok: boolean;
  providerId: string;
  providerName: string;
  model: string;
  baseUrl: string;
  endpointUrl: string;
  latencyMs: number;
  llmStatus: string;
  message: string;
  replyPreview: string;
};

export function describeLlmStatus(meta?: LlmMeta): {
  title: string;
  message: string;
  tone: "success" | "error" | "warning";
} | null {
  if (!meta?.llmStatus) {
    return null;
  }

  const status = meta.llmStatus;
  const message = meta.llmMessage ?? "";

  if (status === "success") {
    return {
      title: "LLM 建议已生成",
      message: message || "大模型建议已成功返回。",
      tone: "success"
    };
  }

  if (status === "fallback_rule") {
    return {
      title: "已回退规则生成",
      message: message || "LLM 未返回有效结果，已使用规则逻辑生成内容。",
      tone: "warning"
    };
  }

  const statusLabels: Record<string, string> = {
    not_configured: "LLM 未配置",
    auth_invalid: "LLM 鉴权失败",
    timeout: "LLM 请求超时",
    network: "LLM 网络异常",
    http_error: "LLM 服务异常",
    empty_response: "LLM 空响应",
    parse_error: "LLM 解析失败",
    unsupported_auth: "不支持的鉴权方式",
    not_implemented: "功能尚未接入",
    vision_unsupported: "模型不支持 Vision"
  };

  return {
    title: statusLabels[status] ?? "LLM 调用异常",
    message: message || "请检查 Provider 配置或稍后重试。",
    tone: status === "fallback_rule" ? "warning" : "error"
  };
}

export function llmNoticeTone(
  tone: "success" | "error" | "warning"
): "error" | "success" | "warning" {
  return tone;
}
