"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, useTransition } from "react";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import {
  deleteStoryboardSegment,
  generateStoryboard,
  reorderStoryboard
} from "@/lib/browser-api";
import {
  getStoryboardBeatModeLabel,
  getStoryboardFunctionLabel
} from "@/lib/storyboard-options";
import type { StoryboardBundle } from "@/types/domain";

type StoryboardListClientProps = {
  beatMode: string;
  initialBundle: StoryboardBundle;
  projectId: string;
  selectedThemeId: string;
  selectedTrackName: string;
  targetDurationSec: number;
};

export function StoryboardListClient({
  beatMode,
  initialBundle,
  projectId,
  selectedThemeId,
  selectedTrackName,
  targetDurationSec
}: StoryboardListClientProps) {
  const [bundle, setBundle] = useState(initialBundle);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success";
  } | null>(null);
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  const validationItems = useMemo(
    () => [
      {
        label: "绑定素材",
        value: bundle.validation.allSegmentsBoundToAsset ? "通过" : "未通过"
      },
      {
        label: "地点连续性",
        value: bundle.validation.locationContinuityPassed ? "通过" : "未通过"
      },
      {
        label: "节拍对齐",
        value: bundle.validation.beatAlignmentPassed ? "通过" : "未通过"
      },
      {
        label: "总时长",
        value: `${bundle.validation.totalDurationSec}s`
      }
    ],
    [bundle.validation]
  );

  function showError(message: string) {
    setError(message);
    setNotice({
      title: "操作失败",
      message,
      tone: "error"
    });
  }

  function handleGenerate() {
    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await generateStoryboard(projectId, {
          themeId: selectedThemeId,
          targetDurationSec,
          beatMode,
          selectedTrackName
        });
        setBundle(nextBundle);
        setNotice({
          title: "分镜已更新",
          message: "已根据当前节奏重新生成时间线。"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成分镜失败，请稍后再试。"
        );
      }
    });
  }

  function handleDelete(segmentId: string) {
    const confirmed = window.confirm("删除后这个镜头会从当前时间线中移除，确认继续吗？");
    if (!confirmed) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await deleteStoryboardSegment(projectId, segmentId);
        setBundle(nextBundle);
        setNotice({
          title: "镜头已删除",
          message: "当前分镜列表已经更新。"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "删除镜头失败，请稍后再试。"
        );
      }
    });
  }

  function handleMove(segmentId: string, direction: "up" | "down") {
    const currentIndex = bundle.segments.findIndex((segment) => segment.id === segmentId);
    if (currentIndex === -1) {
      return;
    }

    const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
    if (targetIndex < 0 || targetIndex >= bundle.segments.length) {
      return;
    }

    const orderedIds = bundle.segments.map((segment) => segment.id);
    [orderedIds[currentIndex], orderedIds[targetIndex]] = [
      orderedIds[targetIndex],
      orderedIds[currentIndex]
    ];

    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await reorderStoryboard(projectId, {
          orderedSegmentIds: orderedIds
        });
        setBundle(nextBundle);
        setNotice({
          title: "顺序已更新",
          message: "分镜顺序和时间线已经重新排布。"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "调整顺序失败，请稍后再试。"
        );
      }
    });
  }

  return (
    <>
      <BlockingNotice
        visible={isPending}
        title="正在处理分镜"
        description="正在更新当前时间线，请稍等片刻。"
      />
      <ToastNotice
        visible={Boolean(notice)}
        title={notice?.title ?? ""}
        message={notice?.message ?? ""}
        tone={notice?.tone}
      />

      <div className="space-y-5">
        <div className="rounded-[28px] border border-pine/10 bg-mist/70 p-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-ink">时间线整理区</p>
              <p className="mt-1 text-sm leading-6 text-ink/65">
                先生成基础分镜，再用后插、上移、下移快速整理结构。详细字段修改放到单镜头页完成。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isPending}
                className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "生成中..." : "根据节拍生成分镜"}
              </button>
              <Link
                href={`/projects/${projectId}/storyboard/new`}
                className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-white"
              >
                手工新增分镜
              </Link>
            </div>
          </div>
        </div>

        {error ? (
          <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay">
            {error}
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-4">
          {validationItems.map((item) => (
            <div
              key={item.label}
              className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70"
            >
              {item.label}：{item.value}
            </div>
          ))}
        </div>

        {bundle.segments.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-pine/20 bg-white px-4 py-8 text-center text-sm text-ink/60">
            还没有分镜时间线。请先确认主题和节奏规划，再生成当前项目的分镜。
          </div>
        ) : (
          <div className="space-y-4">
            {bundle.segments.map((segment, index) => {
              const duration = Math.max(0, Number((segment.endTime - segment.startTime).toFixed(2)));

              return (
                <article
                  key={segment.id}
                  className="rounded-[30px] border border-black/5 bg-white/90 p-5 shadow-card transition hover:-translate-y-0.5 hover:shadow-[0_24px_56px_rgba(25,34,41,0.1)]"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="flex min-w-0 items-start gap-4">
                      <div className="flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-[20px] bg-pine text-white shadow-[0_16px_32px_rgba(47,94,82,0.18)]">
                        <span className="text-[11px] uppercase tracking-[0.18em] text-white/70">
                          shot
                        </span>
                        <span className="text-lg font-semibold leading-none">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-full bg-sand px-3 py-1 text-xs font-medium text-ink/65">
                            {segment.startTime}s - {segment.endTime}s
                          </span>
                          <span className="rounded-full bg-mist px-3 py-1 text-xs font-medium text-ink/65">
                            {duration}s
                          </span>
                          <span className="rounded-full bg-mist px-3 py-1 text-xs font-medium text-ink/65">
                            {getStoryboardFunctionLabel(segment.function)}
                          </span>
                        </div>
                        <h3 className="mt-3 text-lg font-semibold text-ink">
                          {segment.shotDescription}
                        </h3>
                        <p className="mt-2 text-sm leading-6 text-ink/65">{segment.subtitle}</p>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/projects/${projectId}/storyboard/${segment.id}/edit`}
                        className="inline-flex rounded-full bg-pine px-4 py-2 text-sm font-medium text-white transition hover:bg-pine/90"
                      >
                        编辑
                      </Link>
                      <Link
                        href={`/projects/${projectId}/storyboard/new?after=${segment.id}`}
                        className="inline-flex rounded-full border border-pine/20 bg-white px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist"
                      >
                        后插一条
                      </Link>
                      <div className="flex items-center rounded-full border border-pine/20 bg-white p-1">
                        <button
                          type="button"
                          onClick={() => handleMove(segment.id, "up")}
                          disabled={isPending || index === 0}
                          className="inline-flex rounded-full px-3 py-1.5 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          上移
                        </button>
                        <button
                          type="button"
                          onClick={() => handleMove(segment.id, "down")}
                          disabled={isPending || index === bundle.segments.length - 1}
                          className="inline-flex rounded-full px-3 py-1.5 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          下移
                        </button>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDelete(segment.id)}
                        className="inline-flex rounded-full border border-clay/20 bg-white px-4 py-2 text-sm font-medium text-clay transition hover:bg-[#fff4ee]"
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-4">
                    <div className="rounded-2xl bg-mist px-4 py-3 text-sm text-ink/70">
                      时间：{segment.startTime}s - {segment.endTime}s
                    </div>
                    <div className="rounded-2xl bg-mist px-4 py-3 text-sm text-ink/70">
                      时长：{duration}s
                    </div>
                    <div className="rounded-2xl bg-mist px-4 py-3 text-sm text-ink/70">
                      素材：{segment.assetId}
                    </div>
                    <div className="rounded-2xl bg-mist px-4 py-3 text-sm text-ink/70">
                      节拍：{getStoryboardBeatModeLabel(segment.beatMode)}
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
