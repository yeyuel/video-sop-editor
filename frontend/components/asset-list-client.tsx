"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useTransition } from "react";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { ConfirmDialog, EmptyState, InlineErrorBanner } from "@/components/ui-primitives";
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
  const router = useRouter();
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
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  function showError(message: string) {
    setError(message);
    setNotice({ title: "操作失败", message, tone: "error" });
  }

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
        router.refresh();
        setNotice({
          title: "素材已删除",
          message: `已移除素材「${confirmAsset.assetId}」。`,
          tone: "success"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "删除素材失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <>
      <BlockingNotice
        visible={isPending}
        title="正在处理素材"
        description="正在更新素材列表，请稍等片刻。"
      />
      <ToastNotice
        visible={Boolean(notice)}
        title={notice?.title ?? ""}
        message={notice?.message ?? ""}
        tone={notice?.tone}
      />

      <div className="space-y-5">
        <div className="rounded-[28px] border border-pine/10 bg-mist/70 p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="max-w-2xl">
              <p className="text-sm font-medium text-ink">素材整理区</p>
              <p className="mt-1 text-sm leading-6 text-ink/65">
                每条素材对应一个可编辑卡片。点击「编辑素材」进入详情页，Enter 也可在聚焦卡片时进入编辑。
              </p>
            </div>
            <Link
              href={`/projects/${projectId}/assets/new`}
              className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90"
            >
              新增素材
            </Link>
          </div>
        </div>

        <InlineErrorBanner message={error} />

        {assets.length === 0 ? (
          <EmptyState message="当前还没有素材，先新增第一条素材。">
            <Link
              href={`/projects/${projectId}/assets/new`}
              className="inline-flex rounded-full bg-pine px-4 py-2 text-sm font-medium text-white transition hover:bg-pine/90"
            >
              新增素材
            </Link>
          </EmptyState>
        ) : (
          <div className="space-y-3">
            {assets.map((asset) => (
              <article
                key={asset.assetId}
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    router.push(`/projects/${projectId}/assets/${asset.assetId}/edit`);
                  }
                }}
                className="rounded-[30px] border border-black/5 bg-white/90 p-5 shadow-card transition hover:-translate-y-0.5 hover:shadow-[0_24px_56px_rgba(25,34,41,0.1)] focus:outline-none focus:ring-2 focus:ring-pine/20"
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
                    onClick={() => {
                      setError("");
                      setConfirmAsset(asset);
                    }}
                    className="inline-flex rounded-full border border-clay/20 bg-white px-4 py-2 text-sm font-medium text-clay transition hover:border-clay/35 hover:bg-[#fff6f2]"
                  >
                    删除素材
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      <ConfirmDialog
        open={Boolean(confirmAsset)}
        subtitle="Delete Asset"
        title="确认删除素材？"
        description={
          confirmAsset
            ? `将删除素材「${confirmAsset.assetId}」。这个操作会真实写入数据库，无法撤回。`
            : ""
        }
        confirmLabel="确认删除"
        confirmTone="danger"
        error={confirmAsset ? error : ""}
        isPending={isPending}
        onConfirm={handleDelete}
        onCancel={() => {
          setConfirmAsset(null);
          setError("");
        }}
      />
    </>
  );
}
