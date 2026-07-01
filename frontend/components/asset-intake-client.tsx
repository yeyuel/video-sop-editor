"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AssetFormPrototype } from "@/components/asset-form-prototype";
import { AssetMediaPreview } from "@/components/asset-media-preview";
import { MediaLibraryPanel } from "@/components/media-library-panel";
import { InlineErrorBanner } from "@/components/ui-primitives";
import { getMediaLibraryHealth, type MediaLibraryNode } from "@/lib/browser-api";
import { mediaKindFromAssetType } from "@/lib/media-preview-utils";

type AssetIntakeClientProps = {
  projectId: string;
  mediaRoot: string;
};

type PreviewContext = {
  relativePath: string;
  mediaType: string;
};

export function AssetIntakeClient({ projectId, mediaRoot }: AssetIntakeClientProps) {
  const [selectedFile, setSelectedFile] = useState<MediaLibraryNode | null>(null);
  const [previewContext, setPreviewContext] = useState<PreviewContext | null>(null);
  const [formEpoch, setFormEpoch] = useState(0);
  const [rescanToken, setRescanToken] = useState(0);
  const [advanceFromPath, setAdvanceFromPath] = useState<string | null>(null);
  const [mediaRootIssue, setMediaRootIssue] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const health = await getMediaLibraryHealth(projectId);
        if (!cancelled && !health.ok) {
          setMediaRootIssue(health.message);
        }
      } catch {
        if (!cancelled) {
          setMediaRootIssue("无法校验素材根目录，请确认后端服务已启动。");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, mediaRoot]);

  const formDefaults = useMemo(() => {
    if (!selectedFile || selectedFile.nodeType !== "file") {
      return undefined;
    }
    return {
      relativePath: selectedFile.relativePath,
      mediaType: selectedFile.mediaType ?? "video",
      location: selectedFile.relativePath.includes("/")
        ? selectedFile.relativePath.split("/")[0]
        : ""
    };
  }, [selectedFile]);

  const previewRelativePath =
    previewContext?.relativePath.trim() ||
    (selectedFile?.nodeType === "file" ? selectedFile.relativePath : "");
  const previewMediaKind = previewContext
    ? mediaKindFromAssetType(previewContext.mediaType, previewContext.relativePath)
    : selectedFile?.nodeType === "file"
      ? selectedFile.mediaKind ?? null
      : null;

  const handleIntakeSaved = useCallback((info: { relativePath: string; assetId: string }) => {
    setFormEpoch((current) => current + 1);
    setAdvanceFromPath(info.relativePath);
    setRescanToken((current) => current + 1);
  }, []);

  const handleAdvanceComplete = useCallback(() => {
    setAdvanceFromPath(null);
  }, []);

  const handleSelectFile = useCallback((file: MediaLibraryNode) => {
    setSelectedFile(file);
    setPreviewContext(null);
  }, []);

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(300px,360px)_minmax(0,1fr)] xl:items-start">
      <aside className="xl:sticky xl:top-28">
        <MediaLibraryPanel
          projectId={projectId}
          mediaRoot={mediaRoot}
          selectedPath={selectedFile?.relativePath}
          onSelectFile={handleSelectFile}
          rescanToken={rescanToken}
          advanceFromPath={advanceFromPath}
          onAdvanceComplete={handleAdvanceComplete}
        />
      </aside>

      <div className="space-y-5 animate-fade-up">
        {mediaRootIssue ? (
          <InlineErrorBanner
            message={`素材根目录不可用：${mediaRootIssue} 请在项目概览/设置中将 mediaRoot 改为本机实际素材文件夹（例如包含「视频」子目录的路径），保存后点击左侧「扫描目录」。`}
          />
        ) : null}
        <AssetMediaPreview
          projectId={projectId}
          relativePath={previewRelativePath || null}
          mediaKind={previewMediaKind}
          displayName={
            selectedFile?.nodeType === "file" ? selectedFile.name : previewRelativePath.split(/[/\\]/).pop()
          }
          showRecordedBadge={Boolean(selectedFile?.nodeType === "file" && selectedFile.hasAsset)}
          emptyMessage="在左侧目录树中选择一个文件，可在此预览并自动带入录入表单。"
        />
        <AssetFormPrototype
          key={`${selectedFile?.relativePath ?? "empty"}-${formEpoch}`}
          mode="create"
          projectId={projectId}
          defaults={formDefaults}
          intakeMode
          onIntakeSaved={handleIntakeSaved}
          onPreviewContextChange={setPreviewContext}
        />
      </div>
    </div>
  );
}
