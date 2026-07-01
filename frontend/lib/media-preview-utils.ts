import { readApiErrorDetail } from "@/lib/api-base";

export type MediaKind = "video" | "image" | "audio";

export async function probeMediaUrl(url: string): Promise<string | null> {
  try {
    const response = await fetch(url, {
      credentials: "include",
      method: "GET",
      headers: { Range: "bytes=0-0" }
    });
    if (response.ok || response.status === 206) {
      return null;
    }
    return readApiErrorDetail(response);
  } catch {
    return "暂时无法连接预览服务，请确认前后端均已启动。";
  }
}

export function mediaKindLabel(
  kind: string | null | undefined,
  style: "short" | "preview" = "short"
): string {
  if (kind === "video") {
    return style === "preview" ? "视频预览" : "视频";
  }
  if (kind === "image") {
    return style === "preview" ? "图片预览" : "图片";
  }
  if (kind === "audio") {
    return style === "preview" ? "音频预览" : "音频";
  }
  return style === "preview" ? "媒体预览" : "文件";
}

export function mediaKindFromExtension(relativePath?: string | null): MediaKind | null {
  const ext = relativePath?.split(".").pop()?.toLowerCase();
  if (!ext) {
    return null;
  }
  if (["mp4", "mov", "avi", "mkv", "webm", "m4v"].includes(ext)) {
    return "video";
  }
  if (["jpg", "jpeg", "png", "webp", "gif", "bmp", "heic"].includes(ext)) {
    return "image";
  }
  if (["mp3", "wav", "aac", "m4a", "flac", "ogg"].includes(ext)) {
    return "audio";
  }
  return null;
}

export function mediaKindFromAssetType(
  mediaType: string,
  relativePath?: string | null
): MediaKind | null {
  if (mediaType === "photo") {
    return "image";
  }
  if (mediaType === "audio") {
    return "audio";
  }
  if (["video", "drone_video", "mobile_video", "camera_video"].includes(mediaType)) {
    return "video";
  }
  return mediaKindFromExtension(relativePath);
}
