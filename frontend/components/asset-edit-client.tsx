"use client";

import { useState } from "react";

import { AssetFormPrototype } from "@/components/asset-form-prototype";
import { AssetMediaPreview } from "@/components/asset-media-preview";
import { mediaKindFromAssetType } from "@/lib/media-preview-utils";
import type { Asset } from "@/types/domain";

type AssetPreviewContext = {
  relativePath: string;
  mediaType: string;
};

type AssetEditClientProps = {
  projectId: string;
  asset: Asset;
};

export function AssetEditClient({ projectId, asset }: AssetEditClientProps) {
  const [previewContext, setPreviewContext] = useState<AssetPreviewContext>({
    relativePath: asset.relativePath,
    mediaType: asset.mediaType
  });

  const mediaKind = mediaKindFromAssetType(
    previewContext.mediaType,
    previewContext.relativePath
  );

  return (
    <div className="space-y-5 animate-fade-up">
      <AssetMediaPreview
        projectId={projectId}
        relativePath={previewContext.relativePath.trim() || null}
        mediaKind={mediaKind}
        displayName={asset.assetId}
        showRecordedBadge
        emptyMessage="填写素材相对路径后，可在此预览对应文件，便于核对画面内容。"
      />
      <AssetFormPrototype
        key={`${asset.assetId}-${asset.visionAnalysisStatus}-${(asset.visionPrefilledFields ?? []).join(",")}`}
        mode="edit"
        projectId={projectId}
        asset={asset}
        onPreviewContextChange={setPreviewContext}
      />
    </div>
  );
}
