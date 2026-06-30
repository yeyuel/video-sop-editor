"use client";

import { useEffect, useState } from "react";

import { InlineErrorBanner } from "@/components/ui-primitives";
import { getMediaPosterUrl, getMediaPreviewUrl } from "@/lib/browser-api";
import { readApiErrorDetail } from "@/lib/api-base";
import type { MediaLibraryNode } from "@/lib/browser-api";
import type { MediaPreviewQuality } from "@/lib/browser-api";

type MediaPreviewPanelProps = {
  projectId: string;
  file: MediaLibraryNode | null;
};

function kindLabel(kind?: string | null) {
  if (kind === "video") return "视频预览";
  if (kind === "image") return "图片预览";
  if (kind === "audio") return "音频预览";
  return "媒体预览";
}

async function probeMediaUrl(url: string): Promise<string | null> {
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

export function MediaPreviewPanel({ projectId, file }: MediaPreviewPanelProps) {
  const [quality, setQuality] = useState<MediaPreviewQuality>("fast");
  const [videoReady, setVideoReady] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [probeError, setProbeError] = useState<string | null>(null);

  useEffect(() => {
    setVideoReady(false);
    setVideoError(null);
    setProbeError(null);
  }, [file?.relativePath, quality]);

  useEffect(() => {
    if (!file || file.nodeType !== "file") {
      return;
    }

    let cancelled = false;
    const previewUrl = getMediaPreviewUrl(
      projectId,
      file.relativePath,
      file.mediaKind === "video" ? { quality } : undefined
    );
    const posterUrl =
      file.mediaKind === "video" ? getMediaPosterUrl(projectId, file.relativePath) : null;

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
  }, [file, projectId, quality]);

  if (!file || file.nodeType !== "file") {
    return (
      <div className="surface-muted flex min-h-[220px] flex-col justify-center px-6 py-8">
        <p className="text-sm font-medium text-ink/80">预览区</p>
        <p className="mt-2 max-w-lg text-sm leading-7 text-ink/55">
          在左侧目录树中选择一个文件，可在此预览并自动带入录入表单。
        </p>
      </div>
    );
  }

  const isVideo = file.mediaKind === "video";
  const previewUrl = getMediaPreviewUrl(
    projectId,
    file.relativePath,
    isVideo ? { quality } : undefined
  );
  const posterUrl = isVideo ? getMediaPosterUrl(projectId, file.relativePath) : null;
  const displayError = probeError ?? videoError;

  return (
    <div className="surface-panel overflow-hidden p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-pine/70">
            {kindLabel(file.mediaKind)}
          </p>
          <h3 className="mt-1.5 truncate text-lg font-semibold tracking-tight text-ink">
            {file.name}
          </h3>
          <p className="mt-1 break-all text-xs leading-5 text-ink/45">{file.relativePath}</p>
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
          {file.hasAsset ? (
            <span className="badge">已录入素材库</span>
          ) : null}
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
                alt={`${file.name} 封面`}
                className="max-h-[380px] w-full object-contain"
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
              className={`max-h-[380px] w-full bg-black object-contain ${videoReady && !probeError ? "" : "absolute inset-0 opacity-0"}`}
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
        {file.mediaKind === "image" && !probeError ? (
          <img
            key={previewUrl}
            alt={file.name}
            className="max-h-[380px] w-full object-contain"
            src={previewUrl}
          />
        ) : null}
        {file.mediaKind === "audio" && !probeError ? (
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
