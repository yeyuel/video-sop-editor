import type {
  Asset,
  AssetVisionPrefill,
  ExportDocument,
  ExportPlan,
  LlmVisionCapability,
  NarrativeTheme,
  Project,
  RhythmPlan,
  StoryboardBundle,
  StoryboardSegment
} from "@/types/domain";
import type {
  ApiEnvelopeWithMeta,
  LlmMeta,
  LlmModelOption,
  LlmProvider,
  LlmStatus,
  LlmTestResult
} from "@/lib/llm-status";
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
    credentials: "include",
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
    credentials: "include",
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
  jianyingDraftRoot?: string;
  status?: string;
  validateLocationOrder?: boolean;
  allowAssetReuse?: boolean;
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

export type MediaLibraryNode = {
  name: string;
  relativePath: string;
  nodeType: "directory" | "file";
  mediaKind?: "video" | "image" | "audio" | null;
  mediaType?: string | null;
  sizeBytes?: number;
  hasAsset?: boolean;
  children?: MediaLibraryNode[];
};

export type MediaLibraryScanResult = {
  mediaRoot: string;
  fileCount: number;
  directoryCount: number;
  truncated: boolean;
  tree: MediaLibraryNode;
};

export type MediaLibraryHealth = {
  ok: boolean;
  mediaRoot: string;
  message: string;
};

export function getMediaLibraryHealth(projectId: string): Promise<MediaLibraryHealth> {
  return request<MediaLibraryHealth>(`/projects/${projectId}/assets/media-library/health`);
}

export function scanMediaLibrary(projectId: string): Promise<MediaLibraryScanResult> {
  return request<MediaLibraryScanResult>(`/projects/${projectId}/assets/media-library/scan`);
}

export type MediaPreviewQuality = "fast" | "original";

export function getMediaPreviewUrl(
  projectId: string,
  relativePath: string,
  options?: { quality?: MediaPreviewQuality }
): string {
  const query = new URLSearchParams({ relativePath });
  if (options?.quality) {
    query.set("quality", options.quality);
  }
  return `${getBrowserApiBaseUrl()}/projects/${projectId}/assets/media-library/preview?${query.toString()}`;
}

export function getMediaPosterUrl(projectId: string, relativePath: string): string {
  const query = new URLSearchParams({ relativePath });
  return `${getBrowserApiBaseUrl()}/projects/${projectId}/assets/media-library/poster?${query.toString()}`;
}

export function getAssetVisionCapability(
  projectId: string,
  model?: string
): Promise<LlmVisionCapability> {
  const query = model ? `?model=${encodeURIComponent(model)}` : "";
  return request<LlmVisionCapability>(
    `/projects/${projectId}/assets/vision-capability${query}`
  );
}

export function analyzeAssetVisionStream(
  projectId: string,
  assetId: string,
  onEvent: (event: LlmStreamProgressEvent | { type: "complete"; data: AssetVisionPrefill; meta?: LlmMeta } | { type: "error"; message: string }) => void
): Promise<{ data: AssetVisionPrefill; meta?: LlmMeta }> {
  return postLlmStream<AssetVisionPrefill>(
    `/projects/${projectId}/assets/${assetId}/vision-analyze/stream`,
    {},
    onEvent
  );
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

export function recommendBgm(
  projectId: string,
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<RhythmPlan>> {
  if (onProgress) {
    return postLlmStream<RhythmPlan>(
      `/projects/${projectId}/rhythm-plan/bgm-recommend/stream`,
      {},
      (event) => {
        if (event.type === "progress") {
          onProgress(event);
        }
      },
      signal
    );
  }

  return requestWithMeta<RhythmPlan>(`/projects/${projectId}/rhythm-plan/bgm-recommend`, {
    method: "POST"
  });
}

export function generateRhythmPlan(
  projectId: string,
  onProgress?: (event: LlmStreamProgressEvent) => void,
  signal?: AbortSignal
): Promise<RequestWithMetaResult<RhythmPlan>> {
  return recommendBgm(projectId, onProgress, signal);
}

export function selectBgmRecommendation(
  projectId: string,
  recommendationId: string
): Promise<RhythmPlan> {
  return request<RhythmPlan>(`/projects/${projectId}/rhythm-plan/bgm-selection`, {
    method: "PUT",
    body: JSON.stringify({ recommendationId })
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

export function getLlmProviderModels(
  providerId: string,
  options?: { live?: boolean; authType?: string }
): Promise<LlmModelOption[]> {
  const params = new URLSearchParams();
  if (options?.live) {
    params.set("live", "true");
  }
  if (options?.authType) {
    params.set("auth_type", options.authType);
  }
  const query = params.toString();
  return requestLlmAdmin<LlmModelOption[]>(
    `/providers/${providerId}/models${query ? `?${query}` : ""}`
  );
}

export function getLlmVisionCapability(model?: string): Promise<LlmVisionCapability> {
  const query = model ? `?model=${encodeURIComponent(model)}` : "";
  return requestLlmAdmin<LlmVisionCapability>(`/vision-capability${query}`);
}

export function getLlmStatus(): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>("/status");
}

export type LlmAuditLog = {
  id: string;
  userId: string;
  endpoint: string;
  providerId: string;
  model: string;
  status: string;
  tokenEstimate: number;
  message: string;
  createdAt: string;
};

export function getLlmAuditLogs(limit = 20): Promise<LlmAuditLog[]> {
  return requestLlmAdmin<LlmAuditLog[]>(`/audit-logs?limit=${limit}`);
}

export type LlmOAuthStart = {
  authorizationUrl: string;
  state: string;
  message: string;
  requiresPoll?: boolean;
};

export function startLlmOAuth(providerId: string): Promise<LlmOAuthStart> {
  return requestLlmAdmin<LlmOAuthStart>(`/providers/${providerId}/oauth/start`, {
    method: "POST"
  });
}

export function startLlmSubscriptionOAuth(
  providerId: string,
  authType: "codex_oauth" | "gemini_subscription"
): Promise<LlmOAuthStart> {
  return requestLlmAdmin<LlmOAuthStart>(
    `/providers/${providerId}/subscription-oauth/start?auth_type=${encodeURIComponent(authType)}`,
    { method: "POST" }
  );
}

export function pollLlmSubscriptionOAuth(
  providerId: string,
  state: string
): Promise<{ status: string; message: string; configured: boolean; authType: string }> {
  return requestLlmAdmin<{ status: string; message: string; configured: boolean; authType: string }>(
    `/providers/${providerId}/subscription-oauth/poll?state=${encodeURIComponent(state)}`
  );
}

export function completeLlmSubscriptionOAuthCallback(
  providerId: string,
  authType: "codex_oauth" | "gemini_subscription",
  payload: { code: string; state: string }
): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>(
    `/providers/${providerId}/subscription-oauth/callback?auth_type=${encodeURIComponent(authType)}`,
    {
      method: "POST",
      body: JSON.stringify(payload)
    }
  );
}

export function revokeLlmSubscriptionOAuth(
  providerId: string,
  authType: "codex_oauth" | "gemini_subscription"
): Promise<{ revoked: boolean; message: string }> {
  return requestLlmAdmin<{ revoked: boolean; message: string }>(
    `/providers/${providerId}/subscription-oauth/revoke?auth_type=${encodeURIComponent(authType)}`,
    { method: "POST" }
  );
}

export function completeLlmOAuthCallback(
  providerId: string,
  payload: { code: string; state: string }
): Promise<LlmStatus> {
  return requestLlmAdmin<LlmStatus>(`/providers/${providerId}/oauth/callback`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function revokeLlmOAuth(providerId: string): Promise<{ revoked: boolean; message: string }> {
  return requestLlmAdmin<{ revoked: boolean; message: string }>(
    `/providers/${providerId}/oauth/revoke`,
    { method: "POST" }
  );
}

export function previewExport(
  projectId: string,
  format: "markdown" | "json" | "yaml" | "csv" | "capcut" | "edl"
): Promise<ExportDocument> {
  return request<ExportDocument>(`/projects/${projectId}/exports/${format}`, {
    method: "POST"
  });
}

export type CapcutExportDefaults = {
  defaultDraftRoot: string;
  configuredDraftRoot: string;
  effectiveDraftRoot: string;
};

export type CapcutDraftDeployResult = {
  projectId: string;
  draftRoot: string;
  draftFolderName: string;
  draftFolderPath: string;
  files: string[];
  bgmIncluded: boolean;
  message: string;
};

export class CapcutDraftConflictError extends Error {
  draftFolderPath: string;

  constructor(message: string, draftFolderPath: string) {
    super(message);
    this.name = "CapcutDraftConflictError";
    this.draftFolderPath = draftFolderPath;
  }
}

export function fetchCapcutExportDefaults(projectId: string): Promise<CapcutExportDefaults> {
  return request<CapcutExportDefaults>(`/projects/${projectId}/exports/capcut-defaults`);
}

export async function deployCapcutDraft(
  projectId: string,
  payload: { jianyingDraftRoot?: string; persistConfig?: boolean; clearExisting?: boolean }
): Promise<CapcutDraftDeployResult> {
  const response = await fetch(`${getBrowserApiBaseUrl()}/projects/${projectId}/exports/capcut/deploy`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      jianyingDraftRoot: payload.jianyingDraftRoot ?? "",
      persistConfig: payload.persistConfig ?? true,
      clearExisting: payload.clearExisting ?? false
    })
  });

  if (response.status === 409) {
    const detail = await readApiErrorDetail(response);
    const pathMatch = detail.match(/已存在：(.+?)。/);
    throw new CapcutDraftConflictError(detail, pathMatch?.[1] ?? "");
  }

  if (!response.ok) {
    throw new Error(await readApiErrorDetail(response));
  }

  const envelope = (await response.json()) as ApiEnvelope<CapcutDraftDeployResult>;
  return envelope.data;
}

export type ExportImportChange = {
  segmentId: string;
  field: string;
  currentValue: string;
  incomingValue: string;
  action: "update" | "skip" | "unchanged" | string;
};

export type ExportImportResult = {
  schemaVersion: string;
  dryRun: boolean;
  applied: boolean;
  fields: string[];
  conflictStrategy: string;
  changes: ExportImportChange[];
  updateCount: number;
  skippedCount: number;
  unchangedCount: number;
  unknownSegmentIds: string[];
  errors: string[];
};

export type ExportImportPayload = {
  content: string;
  dryRun?: boolean;
  conflictStrategy?: "overwrite" | "skip";
  fields?: string[];
  columnMap?: Record<string, string>;
};

export function importExportJson(
  projectId: string,
  payload: ExportImportPayload
): Promise<ExportImportResult> {
  return request<ExportImportResult>(`/projects/${projectId}/import/export-json`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function importExportCsv(
  projectId: string,
  payload: ExportImportPayload
): Promise<ExportImportResult> {
  return request<ExportImportResult>(`/projects/${projectId}/import/export-csv`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}
