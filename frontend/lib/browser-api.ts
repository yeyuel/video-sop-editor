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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) {
        detail = payload.detail;
      }
    } catch {
      // ignore json parse errors
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const payload = (await response.json()) as ApiEnvelope<T>;
  return payload.data;
}

export type ProjectPayload = {
  name: string;
  destination: string;
  platform: string;
  targetDurationSec: number;
  videoType: string;
  stylePreference: string;
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

export function selectTheme(projectId: string, themeId: string): Promise<NarrativeTheme[]> {
  return request<NarrativeTheme[]>(`/projects/${projectId}/themes/select`, {
    method: "PUT",
    body: JSON.stringify({ themeId })
  });
}

export function generateRhythmPlan(projectId: string): Promise<RhythmPlan> {
  return request<RhythmPlan>(`/projects/${projectId}/rhythm-plan:generate`, {
    method: "POST"
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
    selectedTrackName?: string;
  }
): Promise<StoryboardBundle> {
  return request<StoryboardBundle>(`/projects/${projectId}/storyboard:generate`, {
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

export function saveExportPlan(
  projectId: string,
  payload: ExportPlanPayload
): Promise<ExportPlan> {
  return request<ExportPlan>(`/projects/${projectId}/export-plan`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function previewExport(
  projectId: string,
  format: "markdown" | "json" | "yaml"
): Promise<ExportDocument> {
  return request<ExportDocument>(`/projects/${projectId}/exports/${format}`, {
    method: "POST"
  });
}
