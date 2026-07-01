"use client";

import { useEffect, useState } from "react";

import { InlineErrorBanner } from "@/components/ui-primitives";
import { getMediaPosterUrl, getMediaPreviewUrl, type MediaPreviewQuality } from "@/lib/browser-api";
import {
  mediaKindLabel,
  probeMediaUrl,
  type MediaKind
} from "@/lib/media-preview-utils";

export type AssetMediaPreviewProps = {
  projectId: string;
  relativePath: string | null;
  mediaKind: MediaKind | null;
  displayName?: string;
  showRecordedBadge?: boolean;
  maxHeightClassName?: string;
  emptyMessage?: string;
  className?: string;
};

export function AssetMediaPreview({
  projectId,
  relativePath,
  mediaKind,
  displayName,
  showRecordedBadge = false,
  maxHeightClassName = "max-h-[380px]",
  emptyMessage = "填写或选择素材相对路径后，可在此预览视频、图片或音频。",
  className = ""
}: AssetMediaPreviewProps) {
  const [quality, setQuality] = useState<MediaPreviewQuality>("fast");
  const [videoReady, setVideoReady] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [probeError, setProbeError] = useState<string | null>(null);

  const normalizedPath = relativePath?.trim() ?? "";

  useEffect(() => {
    setVideoReady(false);
    setVideoError(null);
    setProbeError(null);
  }, [normalizedPath, quality, mediaKind]);

  useEffect(() => {
    if (!normalizedPath || !mediaKind) {
      return;
    }

    let cancelled = false;
    const previewUrl = getMediaPreviewUrl(
      projectId,
      normalizedPath,
      mediaKind === "video" ? { quality } : undefined
    );
    const posterUrl =
      mediaKind === "video" ? getMediaPosterUrl(projectId, normalizedPath) : null;

    void (async () => {
      const previewMessage = await probeMediaUrl(previewUrl);
      if (cancelled) {
        return;
      }
      if (previewMessage) {
        setProbeError(previewMessage);
        return;
      }
      if (posterUrl) {
        const posterMessage = await probeMediaUrl(posterUrl);
        if (!cancelled && posterMessage) {
          setProbeError(posterMessage);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [mediaKind, normalizedPath, projectId, quality]);

  if (!normalizedPath || !mediaKind) {
    return (
      <div
        className={`surface-muted flex min-h-[220px] flex-col justify-center px-6 py-8 ${className}`}
      >
        <p className="text-sm font-medium text-ink/80">预览区</p>
        <p className="mt-2 max-w-lg text-sm leading-7 text-ink/55">{emptyMessage}</p>
      </div>
    );
  }

  const isVideo = mediaKind === "video";
  const previewUrl = getMediaPreviewUrl(
    projectId,
    normalizedPath,
    isVideo ? { quality } : undefined
  );
  const posterUrl = isVideo ? getMediaPosterUrl(projectId, normalizedPath) : null;
  const displayError = probeError ?? videoError;
  const title = displayName?.trim() || normalizedPath.split(/[/\\]/).pop() || normalizedPath;

  return (
    <div className={`surface-panel overflow-hidden p-4 md:p-5 ${className}`}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-pine/70">
            {mediaKindLabel(mediaKind, "preview")}
          </p>
          <h3 className="mt-1.5 truncate text-lg font-semibold tracking-tight text-ink">{title}</h3>
          <p className="mt-1 break-all text-xs leading-5 text-ink/45">{normalizedPath}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isVideo ? (
            <div className="flex rounded-full border border-line bg-sand p-0.5 text-xs">
              <button
                type="button"
                className={`rounded-full px-3 py-1.5 transition ${
                  quality === "fast" ? "bg-white text-pine shadow-sm" : "text-ink/55"
                }`}
                onClick={() => setQuality("fast")}
              >
                快速预览
              </button>
              <button
                type="button"
                className={`rounded-full px-3 py-1.5 transition ${
                  quality === "original" ? "bg-white text-pine shadow-sm" : "text-ink/55"
                }`}
                onClick={() => setQuality("original")}
              >
                原画质
              </button>
            </div>
          ) : null}
          {showRecordedBadge ? <span className="badge">已录入素材库</span> : null}
        </div>
      </div>

      {displayError ? (
        <InlineErrorBanner message={`媒体预览不可用：${displayError}`} />
      ) : null}

      <div className="relative overflow-hidden rounded-[1.25rem] border border-ink/10 bg-[#101418] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        {isVideo ? (
          <>
            {!videoReady && posterUrl && !probeError ? (
              <img
                alt={`${title} 封面`}
                className={`${maxHeightClassName} w-full object-contain`}
                src={posterUrl}
              />
            ) : null}
            {!videoReady && !displayError ? (
              <div className="absolute inset-0 flex items-center justify-center bg-black/35 backdrop-blur-[1px]">
                <p className="rounded-full border border-white/10 bg-black/55 px-4 py-2 text-sm text-white/90">
                  {quality === "fast" ? "正在生成低码率预览…" : "正在加载视频…"}
                </p>
              </div>
            ) : null}
            {displayError ? (
              <div className="flex min-h-[220px] items-center justify-center p-6 text-sm text-white/80">
                请检查项目 mediaRoot 是否指向实际素材目录，或在项目设置中更新路径后重新扫描。
              </div>
            ) : null}
            <video
              key={previewUrl}
              controls
              playsInline
              preload="metadata"
              poster={posterUrl ?? undefined}
              className={`${maxHeightClassName} w-full bg-black object-contain ${videoReady && !probeError ? "" : "absolute inset-0 opacity-0"}`}
              src={previewUrl}
              onLoadedData={() => setVideoReady(true)}
              onError={() =>
                setVideoError(
                  quality === "fast"
                    ? "快速预览失败，可切换到「原画质」或确认服务端已安装 ffmpeg。"
                    : "视频加载失败，请检查文件格式或 mediaRoot 路径。"
                )
              }
            />
          </>
        ) : null}
        {mediaKind === "image" && !probeError ? (
          <img
            key={previewUrl}
            alt={title}
            className={`${maxHeightClassName} w-full object-contain`}
            src={previewUrl}
          />
        ) : null}
        {mediaKind === "audio" && !probeError ? (
          <div className="flex min-h-[180px] items-center justify-center bg-gradient-to-br from-pine/20 to-clay/10 p-6">
            <audio key={previewUrl} controls className="w-full max-w-xl" src={previewUrl} />
          </div>
        ) : null}
      </div>
      {isVideo && quality === "fast" && !displayError ? (
        <p className="mt-3 text-xs leading-5 text-ink/45">
          快速预览为 720p 低码率 H.264（无音频），首次选中会转码并缓存，之后加载更快。
        </p>
      ) : null}
    </div>
  );
}
