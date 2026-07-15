"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState, useTransition } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { ConfirmDialog, EmptyState, InlineErrorBanner, ValidationIssuesPanel } from "@/components/ui-primitives";
import {
  deleteStoryboardSegment,
  fillStoryboardVoiceoverFromSubtitles,
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
  getStoryboardAttentionRoleLabel,
  getStoryboardBeatModeLabel,
  getStoryboardFunctionLabel,
  getStoryboardMotionPolicyLabel,
  getStoryboardSubtitlePolicyLabel,
  getStoryboardTransitionPolicyLabel,
  getStoryboardVoiceoverRoleLabel,
  getStoryboardVoiceoverTimingLabel,
  getStoryboardVisualStrengthLabel
} from "@/lib/storyboard-options";
import type { StoryboardBundle } from "@/types/domain";

type StoryboardListClientProps = {
  allowAssetReuse: boolean;
  beatMode: string;
  initialBundle: StoryboardBundle;
  projectId: string;
  selectedThemeId: string;
  selectedTrackName: string;
  targetDurationSec: number;
};

export function StoryboardListClient({
  allowAssetReuse,
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
        label: "镜头复用",
        value: allowAssetReuse
          ? bundle.validation.reusedAssetCount > 0
            ? `${bundle.validation.reusedAssetCount} 素材 / ${bundle.validation.reusedSegmentCount} 段`
            : "已启用"
          : "未启用"
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
    [allowAssetReuse, bundle.validation]
  );

  const assetReuseCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const segment of bundle.segments) {
      counts.set(segment.assetId, (counts.get(segment.assetId) ?? 0) + 1);
    }
    return counts;
  }, [bundle.segments]);

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
        const reuseNote =
          meta?.assetReuseEnabled === "true" ? " 项目已启用镜头复用。" : "";
        if (llmNotice) {
          setNotice({
            title: llmNotice.title,
            message: validationNotice
              ? `${llmNotice.message}${reuseNote} ${validationNotice.message}`
              : `${llmNotice.message}${reuseNote}`,
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

  function handleFillVoiceoverFromSubtitles() {
    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await fillStoryboardVoiceoverFromSubtitles(projectId, {
          overwriteExisting: false,
          role: "narration",
          timing: "follow_segment"
        });
        setBundle(nextBundle);
        router.refresh();
        setNotice({
          title: "口播稿已生成",
          message: "已根据字幕补齐空白口播稿；已有口播内容不会被覆盖。"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成口播稿失败，请稍后再试。"
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
        <div className="surface-muted p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <p className="text-sm font-medium text-ink">时间线整理区</p>
              <p className="mt-1 text-sm leading-6 text-ink/65">
                {allowAssetReuse
                  ? "当前项目已启用镜头复用：生成时会轮用素材以尽量贴近目标时长，并在列表标注复用镜头。"
                  : "当前生成规则为「一素材一分镜」。若素材不足，系统会在素材用完时停止生成，并提示补充素材或先将长素材切分后分别录入。"}
              </p>
              <label className="mt-3 inline-flex items-center gap-2 text-sm text-ink/70">
                <input
                  type="checkbox"
                  checked={alignToBeat}
                  onChange={(event) => setAlignToBeat(event.target.checked)}
                  className="h-4 w-4 rounded border-line text-pine focus:ring-pine/20"
                />
                生成时适配节拍
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={isPending || Boolean(llmProgress)}
                className="btn-primary"
              >
                {isPending ? "生成中..." : "生成分镜"}
              </button>
              <button
                type="button"
                onClick={handleGenerateWithLlm}
                disabled={isPending || Boolean(llmProgress)}
                className="btn-ai"
              >
                {isPending ? "处理中..." : "LLM 建议分镜"}
              </button>
              <Link href={`/projects/${projectId}/storyboard/new`} className="btn-secondary">
                手工新增分镜
              </Link>
              <button
                type="button"
                onClick={handleFillVoiceoverFromSubtitles}
                disabled={isPending || Boolean(llmProgress) || bundle.segments.length === 0}
                className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
              >
                从字幕生成口播稿
              </button>
            </div>
          </div>
        </div>

        {error ? <InlineErrorBanner message={error} /> : null}

        <ValidationIssuesPanel issues={bundle.validation.issues} />

        {bundle.validation.message && bundle.validation.issues.length === 0 ? (
          <div className="stat-cell border-pine/15 bg-sand/40">{bundle.validation.message}</div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-6">
          {validationItems.map((item) => (
            <div key={item.label} className="stat-cell">
              {item.label}：{item.value}
            </div>
          ))}
        </div>

        {bundle.segments.length === 0 ? (
          <EmptyState message="还没有分镜时间线。请先确认主题和节奏规划，再生成当前项目的分镜。" />
        ) : (
          <div className="timeline-rail">
            {bundle.segments.map((segment, index) => {
              const duration = Math.max(
                0,
                Number((segment.endTime - segment.startTime).toFixed(2))
              );
              const reuseTotal = assetReuseCounts.get(segment.assetId) ?? 1;
              const reuseOccurrence = bundle.segments
                .slice(0, index + 1)
                .filter((item) => item.assetId === segment.assetId).length;
              const showReuseBadge =
                allowAssetReuse && reuseTotal > 1 && reuseOccurrence > 1;
              const hasSelectionTrace = Boolean(segment.selectionTrace?.trim());

              return (
                <article
                  key={segment.id}
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      router.push(`/projects/${projectId}/storyboard/${segment.id}/edit`);
                    }
                  }}
                  className="surface-panel relative p-5 transition hover:-translate-y-0.5 hover:shadow-card focus:outline-none focus:ring-2 focus:ring-pine/15"
                >
                  <span className="timeline-node">{String(index + 1).padStart(2, "0")}</span>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="stat-pill">
                          {segment.startTime}s – {segment.endTime}s
                        </span>
                        <span className="stat-pill">{duration}s</span>
                        <span className="badge">{getStoryboardFunctionLabel(segment.function)}</span>
                        {segment.attentionRole ? (
                          <span className="badge-ai">
                            {getStoryboardAttentionRoleLabel(segment.attentionRole)}
                          </span>
                        ) : null}
                        {allowAssetReuse && reuseTotal > 1 ? (
                          <span className="badge-ai">×{reuseTotal}</span>
                        ) : null}
                        {showReuseBadge ? <span className="badge">复用</span> : null}
                        {hasSelectionTrace ? <span className="badge-ai">可追溯</span> : null}
                        {segment.voiceoverText?.trim() ? (
                          <span className="badge-ai">口播</span>
                        ) : null}
                      </div>
                      <h3 className="mt-3 text-lg font-semibold text-ink">
                        {segment.shotDescription}
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-ink/65">{segment.subtitle}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/projects/${projectId}/storyboard/${segment.id}/edit`}
                        className="btn-primary px-4 py-2"
                      >
                        编辑
                      </Link>
                      <Link
                        href={`/projects/${projectId}/storyboard/new?after=${segment.id}`}
                        className="btn-secondary px-4 py-2"
                      >
                        后插一条
                      </Link>
                      <div className="flex items-center rounded-full border border-line bg-white p-1">
                        <button
                          type="button"
                          onClick={() => handleMove(segment.id, "up")}
                          disabled={isPending || Boolean(llmProgress) || index === 0}
                          className="btn-ghost px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          上移
                        </button>
                        <button
                          type="button"
                          onClick={() => handleMove(segment.id, "down")}
                          disabled={
                            isPending ||
                            Boolean(llmProgress) ||
                            index === bundle.segments.length - 1
                          }
                          className="btn-ghost px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40"
                        >
                          下移
                        </button>
                      </div>
                      <button type="button" onClick={() => handleDelete(segment.id)} className="btn-danger px-4 py-2">
                        删除
                      </button>
                    </div>
                  </div>

                  <div className="mt-5 grid gap-3 md:grid-cols-3 xl:grid-cols-4">
                    <div className="stat-cell">时间：{segment.startTime}s – {segment.endTime}s</div>
                    <div className="stat-cell">时长：{duration}s</div>
                    <div className="stat-cell">素材：{segment.assetId}</div>
                    <div className="stat-cell">节拍：{getStoryboardBeatModeLabel(segment.beatMode)}</div>
                    <div className="stat-cell">
                      注意力：{getStoryboardAttentionRoleLabel(segment.attentionRole)}
                    </div>
                    <div className="stat-cell">
                      视觉强度：{getStoryboardVisualStrengthLabel(segment.visualStrength)}
                    </div>
                    <div className="stat-cell">
                      动效：{getStoryboardMotionPolicyLabel(segment.motionPolicy)}
                    </div>
                    <div className="stat-cell">
                      转场：{getStoryboardTransitionPolicyLabel(segment.transitionPolicy)}
                    </div>
                    <div className="stat-cell">
                      字幕：{getStoryboardSubtitlePolicyLabel(segment.subtitlePolicy)}
                    </div>
                    <div className="stat-cell">
                      口播角色：{getStoryboardVoiceoverRoleLabel(segment.voiceoverRole)}
                    </div>
                    <div className="stat-cell">
                      口播时间：{getStoryboardVoiceoverTimingLabel(segment.voiceoverTiming)}
                    </div>
                  </div>

                  {segment.voiceoverText?.trim() ? (
                    <details className="mt-4 rounded-3xl border border-pine/10 bg-sand/40 px-4 py-3">
                      <summary className="cursor-pointer select-none text-sm font-semibold text-pine">
                        查看口播预留
                      </summary>
                      <p className="mt-2 text-sm leading-6 text-ink/65">
                        {segment.voiceoverText}
                      </p>
                    </details>
                  ) : null}

                  {hasSelectionTrace ? (
                    <details className="mt-4 rounded-3xl border border-pine/10 bg-mist/60 px-4 py-3">
                      <summary className="cursor-pointer select-none text-sm font-semibold text-pine">
                        查看算法追溯
                      </summary>
                      <p className="mt-2 text-sm leading-6 text-ink/65">
                        {segment.selectionTrace}
                      </p>
                    </details>
                  ) : null}
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
