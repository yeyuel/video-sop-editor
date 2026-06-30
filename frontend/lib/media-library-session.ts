import type { MediaLibraryScanResult } from "@/lib/browser-api";
import { mediaRootsMatch } from "@/lib/media-root-utils";

export type MediaLibrarySession = {
  /** 扫描时的 mediaRoot（用于检测项目设置变更后失效缓存）。 */
  mediaRoot: string;
  expanded: Record<string, boolean>;
  scanResult: MediaLibraryScanResult;
  searchQuery: string;
  updatedAt: number;
};

const SESSION_PREFIX = "media-library-session:";

function storageKey(projectId: string) {
  return `${SESSION_PREFIX}${projectId}`;
}

export function loadMediaLibrarySession(projectId: string): MediaLibrarySession | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(storageKey(projectId));
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as MediaLibrarySession;
    if (!parsed?.scanResult?.tree) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function saveMediaLibrarySession(projectId: string, session: MediaLibrarySession) {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.setItem(
      storageKey(projectId),
      JSON.stringify({
        ...session,
        mediaRoot: session.mediaRoot || session.scanResult.mediaRoot
      })
    );
  } catch {
    // ignore quota / private mode
  }
}

export function isMediaLibrarySessionValid(
  session: MediaLibrarySession,
  currentMediaRoot: string
): boolean {
  const sessionRoot = session.mediaRoot || session.scanResult.mediaRoot;
  return mediaRootsMatch(sessionRoot, currentMediaRoot);
}

export function clearMediaLibrarySession(projectId: string) {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.removeItem(storageKey(projectId));
}
