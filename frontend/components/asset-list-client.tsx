"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { deleteAsset } from "@/lib/browser-api";
import type { Asset } from "@/types/domain";

type AssetListClientProps = {
  projectId: string;
  initialAssets: Asset[];
};

export function AssetListClient({
  projectId,
  initialAssets
}: AssetListClientProps) {
  const mediaTypeLabelMap: Record<string, string> = {
    video: "视频",
    photo: "照片",
    drone_video: "航拍视频",
    mobile_video: "手机视频",
    camera_video: "相机视频"
  };
  const shotTypeLabelMap: Record<string, string> = {
    wide: "大景",
    medium: "中景",
    subject_medium: "中景含人物/主体",
    close_up: "特写",
    human: "人物",
    animal: "动物",
    transition: "转场"
  };

  const [assets, setAssets] = useState(initialAssets);
  const [confirmAsset, setConfirmAsset] = useState<Asset | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleDelete() {
    if (!confirmAsset) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        await deleteAsset(projectId, confirmAsset.assetId);
        setAssets((current) =>
          current.filter((asset) => asset.assetId !== confirmAsset.assetId)
        );
        setConfirmAsset(null);
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "删除素材失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <>
      <div className="space-y-3">
        {assets.map((asset) => (
          <article
            key={asset.assetId}
            className="rounded-2xl border border-black/5 bg-white p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-ink">{asset.assetId}</h3>
                <p className="mt-1 text-sm text-ink/65">
                  {asset.location} · {asset.scene}
                </p>
              </div>
              <div className="rounded-full bg-mist px-3 py-1 text-xs font-medium text-pine">
                {shotTypeLabelMap[asset.shotType] ?? asset.shotType}
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm text-ink/70 md:grid-cols-2">
              <div className="rounded-2xl bg-sand/55 px-4 py-3">
                相对路径：{asset.relativePath || "待补充"}
              </div>
              <div className="rounded-2xl bg-sand/55 px-4 py-3">
                视频类型：{mediaTypeLabelMap[asset.mediaType] ?? asset.mediaType} · 建议时长：
                {asset.suggestedDurationSec}s
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link
                href={`/projects/${projectId}/assets/${asset.assetId}/edit`}
                className="inline-flex rounded-full bg-pine px-4 py-2 text-sm font-medium text-white transition hover:bg-pine/90"
              >
                编辑素材
              </Link>
              <button
                type="button"
                onClick={() => setConfirmAsset(asset)}
                className="inline-flex rounded-full border border-clay/20 bg-white px-4 py-2 text-sm font-medium text-clay transition hover:border-clay/35 hover:bg-[#fff6f2]"
              >
                删除素材
              </button>
            </div>
          </article>
        ))}
        {assets.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-pine/20 bg-white px-4 py-8 text-center text-sm text-ink/60">
            当前还没有素材，先新增第一条素材。
          </div>
        ) : null}
      </div>

      {confirmAsset ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-6">
          <div className="w-full max-w-md rounded-xl2 border border-black/5 bg-white p-6 shadow-card">
            <p className="text-xs uppercase tracking-[0.22em] text-clay/80">Delete Asset</p>
            <h3 className="mt-3 text-2xl font-semibold text-ink">确认删除素材？</h3>
            <p className="mt-3 text-sm leading-6 text-ink/70">
              将删除素材“{confirmAsset.assetId}”。这个操作会真实写入数据库，无法撤回。
            </p>
            {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleDelete}
                disabled={isPending}
                className="inline-flex rounded-full bg-clay px-5 py-3 text-sm font-medium text-white transition hover:bg-clay/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "删除中..." : "确认删除"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmAsset(null)}
                disabled={isPending}
                className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
