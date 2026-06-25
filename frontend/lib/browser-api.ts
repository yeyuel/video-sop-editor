import type {
  Asset,
  ExportDocument,
  ExportPlan,
  NarrativeTheme,
  Project,
  RhythmPlan,
  StoryboardBundle,
  StoryboardSegment
} from "@/types/domain";
import type { ApiEnvelopeWithMeta, LlmMeta, LlmProvider, LlmStatus, LlmTestResult } from "@/lib/llm-status";
import { getBrowserApiBaseUrl, readApiErrorDetail } from "@/lib/api-base";
import { postLlmStream, postLlmStreamFormData, type LlmStreamProgressEvent } from "@/lib/llm-stream";

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  meta?: LlmMeta & Record<string, string>;
};

export type RequestWithMetaResult<T> = {
  data: T;
  meta?: LlmMeta;
};

async function requestWithMeta<T>(
  path: string,
  init?: RequestInit
): Promise<RequestWithMetaResult<T>> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${getBrowserApiBaseUrl()}${path}`, {
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }

  if (response.status === 204) {
    return { data: undefined as T };
  }

  const payload = (await response.json()) as ApiEnvelopeWithMeta<T>;
  return { data: payload.data, meta: payload.meta };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const result = await requestWithMeta<T>(path, init);
  return result.data;
}

async function requestLlmAdminWithMeta<T>(
  path: string,
  init?: RequestInit
): Promise<RequestWithMetaResult<T>> {
  const response = await fetch(`/api/llm${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }

  const payload = (await response.json()) as ApiEnvelopeWithMeta<T>;
  return { data: payload.data, meta: payload.meta };
}

async function requestLlmAdmin<T>(path: string, init?: RequestInit): Promise<T> {
  const result = await requestLlmAdminWithMeta<T>(path, init);
  return result.data;
}

export type ProjectPayload = {
  name: string;
  destination: string;
  platform: string;
  targetDurationSec: number;
  videoType: string;
  stylePreference: string;
  styleNotes: string;
  routeText: string;
  mediaRoot: string;
  status?: string;
};

export type AssetPayload = {
  location: string;
  scene: string;
  relativePath: string;
  mediaType: string;
  shotType: string;
  emotionTags: string[];
  visualTags: string[];
  informationDensity: string;
  suggestedDurationSec: number;
  functionTags: string[];
};

export type RhythmPlanPayload = RhythmPlan;

export type StoryboardSavePayload = {
  themeId?: string;
  segments: StoryboardSegment[];
};

export type StoryboardInsertPayload = {
  themeId?: string;
  afterSegmentId?: string;
  segment: StoryboardSegment;
};

export type StoryboardReorderPayload = {
  orderedSegmentIds: string[];
};

export type ExportPlanPayload = ExportPlan;

export function createProject(payload: ProjectPayload): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateProject(projectId: string, payload: ProjectPayload): Promise<Project> {
  return request<Project>(`/projects/${projectId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteProject(projectId: string): Promise<void> {
  return request<void>(`/projects/${projectId}`, {
    method: "DELETE"
  });
}

export function createAsset(projectId: string, payload: AssetPayload): Promise<Asset> {
  return request<Asset>(`/projects/${projectId}/assets`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAsset(
  projectId: string,
  assetId: string,
  payload: AssetPayload
): Promise<Asset> {
  return request<Asset>(`/projects/${projectId}/assets/${assetId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteAsset(projectId: string, assetId: string): Promise<void> {
  return request<void>(`/projects/${projectId}/assets/${assetId}`, {
    method: "DELETE"
  });
}

export function generateThemes(projectId: string, count = 3): Promise<NarrativeTheme[]> {
  return request<NarrativeTheme[]>(`/projects/${projectId}/themes/generate`, {
    method: "POST",
    body: JSON.stringify({ count })
  });
}

export function generateThemesWithLlm(
  projectId: string,
  count = 3,
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<NarrativeTheme[]>> {
  if (onProgress) {
    return postLlmStream<NarrativeTheme[]>(
      `/projects/${projectId}/themes/generate-llm/stream`,
      { count },
      (event) => {
        if (event.type === "progress") {
          onProgress(event);
        }
      },
      signal
    );
  }

  return requestWithMeta<NarrativeTheme[]>(`/projects/${projectId}/themes/generate-llm`, {
    method: "POST",
    body: JSON.stringify({ count })
  });
}

export function selectTheme(projectId: string, themeId: string): Promise<NarrativeTheme[]> {
  return request<NarrativeTheme[]>(`/projects/${projectId}/themes/select`, {
    method: "PUT",
    body: JSON.stringify({ themeId })
  });
}

export function generateRhythmPlan(
  projectId: string,
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<RhythmPlan>> {
  if (onProgress) {
    return postLlmStream<RhythmPlan>(
      `/projects/${projectId}/rhythm-plan/generate/stream`,
      {},
      (event) => {
        if (event.type === "progress") {
          onProgress(event);
        }
      },
      signal
    );
  }

  return requestWithMeta<RhythmPlan>(`/projects/${projectId}/rhythm-plan:generate`, {
    method: "POST"
  });
}

export function uploadRhythmAudio(
  projectId: string,
  file: File,
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<RhythmPlan>> {
  if (onProgress) {
    const formData = new FormData();
    formData.append("audio", file);
    return postLlmStreamFormData<RhythmPlan>(
      `/projects/${projectId}/rhythm-plan/audio-upload/stream`,
      formData,
      (event) => {
        if (event.type === "progress") {
          onProgress(event);
        }
      },
      signal
    );
  }

  const formData = new FormData();
  formData.append("audio", file);
  return requestWithMeta<RhythmPlan>(`/projects/${projectId}/rhythm-plan/audio-upload`, {
    method: "POST",
    body: formData
  });
}

export function deleteRhythmAudio(projectId: string): Promise<RhythmPlan> {
  return request<RhythmPlan>(`/projects/${projectId}/rhythm-plan/audio`, {
    method: "DELETE"
  });
}

export function saveRhythmPlan(projectId: string, payload: RhythmPlanPayload): Promise<RhythmPlan> {
  return request<RhythmPlan>(`/projects/${projectId}/rhythm-plan`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function generateStoryboard(
  projectId: string,
  payload: {
    themeId?: string;
    targetDurationSec?: number;
    beatMode?: string;
    alignToBeat?: boolean;
    selectedTrackName?: string;
  }
): Promise<StoryboardBundle> {
  return request<StoryboardBundle>(`/projects/${projectId}/storyboard:generate`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function generateStoryboardWithLlm(
  projectId: string,
  payload: {
    themeId?: string;
    targetDurationSec?: number;
    beatMode?: string;
    alignToBeat?: boolean;
    selectedTrackName?: string;
  },
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<StoryboardBundle>> {
  if (onProgress) {
    return postLlmStream<StoryboardBundle>(
      `/projects/${projectId}/storyboard/generate-llm/stream`,
      payload,
      (event) => {
        if (event.type === "progress") {
          onProgress(event);
        }
      },
      signal
    );
  }

  return requestWithMeta<StoryboardBundle>(`/projects/${projectId}/storyboard:generate-llm`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function saveStoryboard(
  projectId: string,
  payload: StoryboardSavePayload
): Promise<StoryboardBundle> {
  return request<StoryboardBundle>(`/projects/${projectId}/storyboard`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function updateStoryboardSegment(
  projectId: string,
  segmentId: string,
  payload: StoryboardSegment
): Promise<StoryboardSegment> {
  return request<StoryboardSegment>(`/projects/${projectId}/storyboard/${segmentId}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteStoryboardSegment(
  projectId: string,
  segmentId: string
): Promise<StoryboardBundle> {
  return request<StoryboardBundle>(`/projects/${projectId}/storyboard/${segmentId}`, {
    method: "DELETE"
  });
}

export function insertStoryboardSegment(
  projectId: string,
  payload: StoryboardInsertPayload
): Promise<StoryboardBundle> {
  return request<StoryboardBundle>(`/projects/${projectId}/storyboard/insert`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function reorderStoryboard(
  projectId: string,
  payload: StoryboardReorderPayload
): Promise<StoryboardBundle> {
  return request<StoryboardBundle>(`/projects/${projectId}/storyboard/reorder`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function saveExportPlan(
  projectId: string,
  payload: ExportPlanPayload
): Promise<ExportPlan> {
  return request<ExportPlan>(`/projects/${projectId}/export-plan`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function suggestExportPlanWithLlm(
  projectId: string,
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<ExportPlan>> {
  if (onProgress) {
    return postLlmStream<ExportPlan>(
      `/projects/${projectId}/export-plan/suggest/stream`,
      {},
      (event) => {
        if (event.type === "progress") {
          onProgress(event);
        }
      },
      signal
    );
  }

  return requestWithMeta<ExportPlan>(`/projects/${projectId}/export-plan:suggest`, {
    method: "POST"
  });
}

export type LlmProviderConfigPayload = {
  authType?: string;
  baseUrl: string;
  model: string;
  apiKey?: string;
};

export function getLlmProviderStatus(providerId: string): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>(`/providers/${providerId}/status`);
}

export function saveLlmProviderConfig(
  providerId: string,
  payload: LlmProviderConfigPayload
): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>(`/providers/${providerId}/config`, {
    method: "POST",
    body: JSON.stringify({
      authType: payload.authType ?? "api_key",
      baseUrl: payload.baseUrl,
      model: payload.model,
      apiKey: payload.apiKey ?? ""
    })
  });
}

export function activateLlmProvider(providerId: string): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>(`/providers/${providerId}/activate`, {
    method: "POST"
  });
}

export function testLlmProvider(
  providerId: string,
  payload?: LlmProviderConfigPayload
): Promise<RequestWithMetaResult<LlmTestResult>> {
  return requestLlmAdminWithMeta<LlmTestResult>(`/providers/${providerId}/test`, {
    method: "POST",
    body: JSON.stringify({
      authType: payload?.authType ?? "api_key",
      baseUrl: payload?.baseUrl ?? "",
      model: payload?.model ?? "",
      apiKey: payload?.apiKey ?? ""
    })
  });
}

export function testActiveLlmProvider(): Promise<RequestWithMetaResult<LlmTestResult>> {
  return requestLlmAdminWithMeta<LlmTestResult>("/test", {
    method: "POST"
  });
}

export function getLlmProviders(): Promise<LlmProvider[]> {
  return requestLlmAdmin<LlmProvider[]>("/providers");
}

export function getLlmStatus(): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>("/status");
}

export function previewExport(
  projectId: string,
  format: "markdown" | "json" | "yaml"
): Promise<ExportDocument> {
  return request<ExportDocument>(`/projects/${projectId}/exports/${format}`, {
    method: "POST"
  });
}
