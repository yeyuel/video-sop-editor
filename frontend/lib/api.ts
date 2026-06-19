import { fallbackProjects, fallbackWorkspace } from "@/lib/mock-data";
import type {
  Asset,
  ExportDocument,
  ExportPlan,
  NarrativeTheme,
  Project,
  RhythmPlan,
  StoryboardBundle,
  WorkspaceData
} from "@/types/domain";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function safeFetch<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      cache: "no-store"
    });

    if (!response.ok) {
      return fallback;
    }

    const payload = (await response.json()) as { data: T };
    return payload.data;
  } catch {
    return fallback;
  }
}

export async function getProjects(): Promise<Project[]> {
  return safeFetch<Project[]>("/projects", fallbackProjects);
}

export async function getProject(projectId: string): Promise<Project> {
  return safeFetch<Project>(`/projects/${projectId}`, fallbackWorkspace.project);
}

export async function getWorkspace(projectId: string): Promise<WorkspaceData> {
  return safeFetch<WorkspaceData>(`/projects/${projectId}/workspace`, fallbackWorkspace);
}

export async function getAsset(projectId: string, assetId: string): Promise<Asset> {
  const fallbackAsset =
    fallbackWorkspace.assets.find((item) => item.assetId === assetId) ??
    fallbackWorkspace.assets[0];
  return safeFetch<Asset>(`/projects/${projectId}/assets/${assetId}`, fallbackAsset);
}

export async function getThemes(projectId: string): Promise<NarrativeTheme[]> {
  return safeFetch<NarrativeTheme[]>(`/projects/${projectId}/themes`, fallbackWorkspace.themes);
}

export async function getRhythmPlan(projectId: string): Promise<RhythmPlan | null> {
  return safeFetch<RhythmPlan | null>(
    `/projects/${projectId}/rhythm-plan`,
    fallbackWorkspace.rhythmPlan
  );
}

export async function getStoryboard(projectId: string): Promise<StoryboardBundle> {
  return safeFetch<StoryboardBundle>(`/projects/${projectId}/storyboard`, {
    segments: fallbackWorkspace.storyboard,
    validation: fallbackWorkspace.storyboardValidation
  });
}

export async function getExportPlan(projectId: string): Promise<ExportPlan | null> {
  return safeFetch<ExportPlan | null>(
    `/projects/${projectId}/export-plan`,
    fallbackWorkspace.exportPlan
  );
}

export async function getExportPreview(
  projectId: string,
  format: "markdown" | "json" | "yaml"
): Promise<ExportDocument> {
  return safeFetch<ExportDocument>(
    `/projects/${projectId}/exports/${format}`,
    {
      projectId,
      format,
      fileName: `${projectId}-timeline.${format === "markdown" ? "md" : format}`,
      content: ""
    }
  );
}
