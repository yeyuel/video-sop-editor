"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { ConfirmDialog, EmptyState, InlineErrorBanner, ValidationIssuesPanel } from "@/components/ui-primitives";
import {
  deleteStoryboardSegment,
  generateStoryboard,
  generateStoryboardWithLlm,
  reorderStoryboard
} from "@/lib/browser-api";
import {
  applyLlmProgressEvent,
  createLlmProgressState,
  STORYBOARD_LLM_STAGES,
  type LlmProgressViewState
} from "@/lib/llm-progress-stages";
import { describeLlmStatus, llmNoticeTone } from "@/lib/llm-status";
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
  const router = useRouter();
  const [bundle, setBundle] = useState(initialBundle);
  const [alignToBeat, setAlignToBeat] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [deleteSegmentId, setDeleteSegmentId] = useState("");
  const [isPending, startTransition] = useTransition();
  const [llmProgress, setLlmProgress] = useState<LlmProgressViewState | null>(null);

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
        label: "素材绑定",
        value: bundle.validation.allSegmentsBoundToAsset ? "通过" : "未通过"
      },
      {
        label: "地点连续性",
        value: bundle.validation.locationOrderValidationEnabled
          ? bundle.validation.locationContinuityPassed
            ? "通过"
            : "未通过"
          : "未启用"
      },
      {
        label: "节拍适配",
        value: bundle.validation.beatAdaptationEnabled
          ? bundle.validation.beatAlignmentPassed
            ? "已对齐"
            : "未对齐"
          : "未启用"
      },
      {
        label: "目标时长",
        value: bundle.validation.durationWithinTolerance
          ? "在容差内"
          : bundle.validation.targetDurationReached
            ? "已达到"
            : "素材不足"
      },
      {
        label: "时长偏差",
        value: `${bundle.validation.durationDeltaSec >= 0 ? "+" : ""}${bundle.validation.durationDeltaSec}s`
      },
      {
        label: "未绑定镜头",
        value:
          bundle.validation.unboundSegmentCount === 0
            ? "无"
            : `${bundle.validation.unboundSegmentCount} 个`
      },
      {
        label: "当前总时长",
        value: `${bundle.validation.totalDurationSec}s / ${bundle.validation.targetDurationSec}s`
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

  function showValidationNotice(nextBundle: StoryboardBundle, alignToBeatEnabled: boolean) {
    const validation = nextBundle.validation;
    const warnings: string[] = [];
    if (!validation.allSegmentsBoundToAsset) {
      warnings.push("存在未绑定素材的镜头");
    }
    if (
      validation.locationOrderValidationEnabled &&
      !validation.locationContinuityPassed
    ) {
      warnings.push("地点顺序未通过连续性校验");
    }
    if (
      alignToBeatEnabled &&
      validation.beatAdaptationEnabled &&
      !validation.beatAlignmentPassed
    ) {
      warnings.push("镜头起止点未完全落在节拍点上");
    }
    if (warnings.length === 0) {
      return null;
    }
    return {
      title: "分镜校验提示",
      message: `${warnings.join("；")}。${validation.message}`,
      tone: "warning" as const
    };
  }

  function handleGenerate() {
    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await generateStoryboard(projectId, {
          themeId: selectedThemeId,
          targetDurationSec,
          beatMode,
          alignToBeat,
          selectedTrackName
        });
        setBundle(nextBundle);
        router.refresh();
        const validationNotice = showValidationNotice(nextBundle, alignToBeat);
        if (validationNotice) {
          setNotice(validationNotice);
        } else {
          setNotice({
            title: "分镜已更新",
            message: nextBundle.validation.message || "当前时间线已经重新生成。"
          });
        }
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成分镜失败，请稍后再试。"
        );
      }
    });
  }

  function handleGenerateWithLlm() {
    setError("");
    setLlmProgress(createLlmProgressState("LLM 分镜建议", STORYBOARD_LLM_STAGES));
    startTransition(async () => {
      try {
        const { data: nextBundle, meta } = await generateStoryboardWithLlm(
          projectId,
          {
            themeId: selectedThemeId,
            targetDurationSec,
            beatMode,
            alignToBeat,
            selectedTrackName
          },
          (event) => {
            setLlmProgress((current) =>
              current ? applyLlmProgressEvent(current, event) : current
            );
          }
        );
        setBundle(nextBundle);
        router.refresh();
        const validationNotice = showValidationNotice(nextBundle, alignToBeat);
        const llmNotice = describeLlmStatus(meta);
        if (llmNotice) {
          setNotice({
            title: llmNotice.title,
            message: validationNotice
              ? `${llmNotice.message} ${validationNotice.message}`
              : llmNotice.message,
            tone: llmNoticeTone(llmNotice.tone)
          });
        } else if (validationNotice) {
          setNotice(validationNotice);
        } else {
          setNotice({
            title: "LLM 分镜建议已更新",
            message: nextBundle.validation.message || "当前时间线已经按 LLM 建议重新生成。"
          });
        }
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "LLM 分镜建议生成失败，请稍后再试。"
        );
      } finally {
        setLlmProgress(null);
      }
    });
  }

  function handleDelete(segmentId: string) {
    setError("");
    setDeleteSegmentId(segmentId);
  }

  function confirmDelete() {
    if (!deleteSegmentId) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await deleteStoryboardSegment(projectId, deleteSegmentId);
        setBundle(nextBundle);
        setDeleteSegmentId("");
        router.refresh();
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
        router.refresh();
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
        visible={isPending && !llmProgress}
        title="正在处理分镜"
        description="正在更新当前时间线，请稍等片刻。"
      />
      <LlmProgressOverlay
        state={llmProgress ?? createLlmProgressState("", STORYBOARD_LLM_STAGES)}
        visible={Boolean(llmProgress)}
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
            <div className="max-w-2xl">
              <p className="text-sm font-medium text-ink">时间线整理区</p>
              <p className="mt-1 text-sm leading-6 text-ink/65">
                当前生成规则已按一期逻辑收敛为“默认不重复使用素材”。如果素材不足，系统会在素材用完时停止生成，并提示你补充素材或先把长素材切分后分别录入。
              </p>
              <label className="mt-3 inline-flex items-center gap-2 text-sm text-ink/70">
                <input
                  type="checkbox"
                  checked={alignToBeat}
                  onChange={(event) => setAlignToBeat(event.target.checked)}
                  className="h-4 w-4 rounded border-pine/30 text-pine focus:ring-pine"
                />
                生成时适配节拍
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isPending || Boolean(llmProgress)}
                className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "生成中..." : "生成分镜"}
              </button>
              <button
                type="button"
                onClick={handleGenerateWithLlm}
                disabled={isPending || Boolean(llmProgress)}
                className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-white disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "处理中..." : "LLM 建议分镜"}
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

        {error ? <InlineErrorBanner message={error} /> : null}

        <ValidationIssuesPanel issues={bundle.validation.issues} />

        {bundle.validation.message && bundle.validation.issues.length === 0 ? (
          <div className="rounded-2xl border border-pine/10 bg-sand/45 px-4 py-3 text-sm text-ink/70">
            {bundle.validation.message}
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-5">
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
          <EmptyState message="还没有分镜时间线。请先确认主题和节奏规划，再生成当前项目的分镜。" />
        ) : (
          <div className="space-y-4">
            {bundle.segments.map((segment, index) => {
              const duration = Math.max(
                0,
                Number((segment.endTime - segment.startTime).toFixed(2))
              );

              return (
                <article
                  key={segment.id}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      router.push(`/projects/${projectId}/storyboard/${segment.id}/edit`);
                    }
                  }}
                  className="rounded-[30px] border border-black/5 bg-white/90 p-5 shadow-card transition hover:-translate-y-0.5 hover:shadow-[0_24px_56px_rgba(25,34,41,0.1)] focus:outline-none focus:ring-2 focus:ring-pine/20"
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
                          disabled={isPending || Boolean(llmProgress) || index === 0}
                          className="inline-flex rounded-full px-3 py-1.5 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          上移
                        </button>
                        <button
                          type="button"
                          onClick={() => handleMove(segment.id, "down")}
                          disabled={isPending || Boolean(llmProgress) || index === bundle.segments.length - 1}
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

      <ConfirmDialog
        open={Boolean(deleteSegmentId)}
        subtitle="Delete Segment"
        title="确认删除镜头？"
        description="删除后这个镜头会从当前时间线中移除，确认继续吗？"
        confirmLabel="确认删除"
        confirmTone="danger"
        error={error}
        isPending={isPending}
        onConfirm={confirmDelete}
        onCancel={() => {
          setDeleteSegmentId("");
          setError("");
        }}
      />
    </>
  );
}
