"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent, KeyboardEvent } from "react";
import { useEffect, useState, useTransition } from "react";
import { AssetSelector } from "@/components/asset-selector";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { TimeSecondsInput } from "@/components/time-seconds-input";
import { InlineErrorBanner } from "@/components/ui-primitives";
import { insertStoryboardSegment, updateStoryboardSegment } from "@/lib/browser-api";
import {
  storyboardAttentionRoleOptions,
  storyboardBeatModeOptions,
  storyboardFunctionOptions,
  storyboardMotionPolicyOptions,
  storyboardSubtitlePolicyOptions,
  storyboardTransitionPolicyOptions,
  storyboardVoiceoverRoleOptions,
  storyboardVoiceoverTimingOptions,
  storyboardVisualStrengthOptions
} from "@/lib/storyboard-options";
import { parseTimeSeconds, validateTimeSeconds } from "@/lib/time-input";
import {
  isOnBeat,
  resolveSnappedSegmentTimes,
  sliceBeatPointsInRange
} from "@/lib/beat-snap";
import type { Asset, StoryboardSegment } from "@/types/domain";

type StoryboardSegmentEditorClientProps = {
  afterSegmentId?: string;
  assets: Asset[];
  backHref: string;
  mode?: "create" | "edit";
  projectId: string;
  rhythmBeatPoints?: number[];
  segment: StoryboardSegment;
  targetDurationSec: number;
  themeId?: string;
};

function numberListToText(value: number[]) {
  return value.join(", ");
}

function parseNumberList(value: string) {
  return value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => !Number.isNaN(item));
}

export function StoryboardSegmentEditorClient({
  afterSegmentId,
  assets,
  backHref,
  mode = "edit",
  projectId,
  rhythmBeatPoints = [],
  segment,
  targetDurationSec,
  themeId
}: StoryboardSegmentEditorClientProps) {
  const router = useRouter();
  const [form, setForm] = useState(segment);
  const [startTimeText, setStartTimeText] = useState(segment.startTime.toString());
  const [endTimeText, setEndTimeText] = useState(segment.endTime.toString());
  const [beatPointsText, setBeatPointsText] = useState(numberListToText(segment.beatPoints));
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{ message: string; title: string } | null>(null);
  const [isPending, startTransition] = useTransition();
  const beatModeEnabled = Boolean(form.beatMode && form.beatMode !== "none");
  const beatSnapEnabled = beatModeEnabled && rhythmBeatPoints.length >= 2;
  const parsedStartTime = parseTimeSeconds(startTimeText, {
    min: 0,
    max: targetDurationSec
  });

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timer = window.setTimeout(() => setNotice(null), 2400);
    return () => window.clearTimeout(timer);
  }, [notice]);

  useEffect(() => {
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape" && !isPending) {
        router.push(backHref);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [backHref, isPending, router]);

  function showError(message: string) {
    setError(message);
    setNotice({ title: "保存失败", message });
  }

  function applySnapToBothTimes() {
    const snapped = resolveSnappedSegmentTimes(
      startTimeText,
      endTimeText,
      rhythmBeatPoints,
      targetDurationSec
    );
    if (!snapped) {
      showError("无法吸附到节拍，请确认节奏页已有足够节拍点。");
      return;
    }

    setStartTimeText(snapped.startTimeText);
    setEndTimeText(snapped.endTimeText);
    setBeatPointsText(snapped.beatPointsText);
    setError("");
  }

  function resolveSubmitTimes():
    | {
        beatPointsText: string;
        endTimeText: string;
        startTimeText: string;
      }
    | null {
    if (!beatSnapEnabled) {
      return {
        startTimeText,
        endTimeText,
        beatPointsText
      };
    }

    return resolveSnappedSegmentTimes(
      startTimeText,
      endTimeText,
      rhythmBeatPoints,
      targetDurationSec
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const resolvedTimes = resolveSubmitTimes();
    if (!resolvedTimes) {
      showError("无法吸附到节拍，请检查开始/结束时间或节奏页节拍点。");
      return;
    }

    const startError = validateTimeSeconds(resolvedTimes.startTimeText, {
      min: 0,
      max: targetDurationSec
    });
    if (startError) {
      showError(startError);
      return;
    }

    const endError = validateTimeSeconds(resolvedTimes.endTimeText, {
      min: 0,
      max: targetDurationSec
    });
    if (endError) {
      showError(endError);
      return;
    }

    const startTime = parseTimeSeconds(resolvedTimes.startTimeText, {
      min: 0,
      max: targetDurationSec
    });
    const endTime = parseTimeSeconds(resolvedTimes.endTimeText, {
      min: 0,
      max: targetDurationSec
    });
    if (startTime === null || endTime === null) {
      showError("请填写有效的开始和结束时间。");
      return;
    }

    if (endTime <= startTime) {
      showError("结束时间必须大于开始时间。");
      return;
    }

    if (
      beatSnapEnabled &&
      (!isOnBeat(startTime, rhythmBeatPoints) || !isOnBeat(endTime, rhythmBeatPoints))
    ) {
      showError("起止时间仍需落在节奏页节拍点上，请使用吸附按钮。");
      return;
    }

    startTransition(async () => {
      try {
        const beatPoints = beatSnapEnabled
          ? sliceBeatPointsInRange(rhythmBeatPoints, startTime, endTime)
          : parseNumberList(resolvedTimes.beatPointsText);

        const payload = {
          ...form,
          startTime,
          endTime,
          beatPoints
        };

        if (mode === "create") {
          await insertStoryboardSegment(projectId, {
            themeId,
            afterSegmentId,
            segment: payload
          });
        } else {
          await updateStoryboardSegment(projectId, form.id, payload);
        }

        router.replace(backHref);
        router.refresh();
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "保存镜头失败，请稍后再试。"
        );
      }
    });
  }

  function handleFormKeyDown(event: KeyboardEvent<HTMLFormElement>) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      event.currentTarget.requestSubmit();
    }
  }

  return (
    <>
      <BlockingNotice
        visible={isPending}
        title={mode === "create" ? "正在新增镜头" : "正在保存镜头"}
        description="保存后会自动返回分镜列表，请稍等片刻。"
      />
      <ToastNotice
        visible={Boolean(notice)}
        title={notice?.title ?? ""}
        message={notice?.message ?? ""}
        tone="error"
      />

      <form
        className="grid gap-5 md:grid-cols-2"
        onSubmit={handleSubmit}
        onKeyDown={handleFormKeyDown}
      >
        <TimeSecondsInput
          label="开始（秒）"
          value={startTimeText}
          max={targetDurationSec}
          beatPoints={rhythmBeatPoints}
          enableBeatSnap={beatSnapEnabled}
          onValueChange={setStartTimeText}
        />
        <TimeSecondsInput
          label="结束（秒）"
          value={endTimeText}
          max={targetDurationSec}
          beatPoints={rhythmBeatPoints}
          beatSnapMin={parsedStartTime !== null ? parsedStartTime + 0.01 : 0}
          enableBeatSnap={beatSnapEnabled}
          onValueChange={setEndTimeText}
        />

        {beatSnapEnabled ? (
          <div className="surface-muted md:col-span-2 flex flex-wrap items-center gap-3 px-4 py-3">
            <p className="text-sm text-ink/70">
              当前使用节奏页 {rhythmBeatPoints.length} 个节拍点。失焦或点击按钮可将时间吸附到最近节拍。
            </p>
            <button type="button" onClick={applySnapToBothTimes} className="btn-secondary px-4 py-2">
              一键吸附起止时间
            </button>
          </div>
        ) : null}

        <div className="md:col-span-2">
          <AssetSelector
            assets={assets}
            projectId={projectId}
            value={form.assetId}
            onChange={(assetId) => setForm({ ...form, assetId })}
          />
        </div>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">功能标签</span>
          <select
            value={form.function}
            onChange={(event) => setForm({ ...form, function: event.target.value })}
            className={`input-field ${form.function ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardFunctionOptions.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={form.function ? "badge" : "stat-pill"}>
              {form.function ? "已设置功能标签" : "当前未设置"}
            </span>
            <p className="text-xs text-ink/55">功能标签为可选项，先不标注也可以保存。</p>
          </div>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">注意力角色</span>
          <select
            value={form.attentionRole}
            onChange={(event) => setForm({ ...form, attentionRole: event.target.value })}
            className={`input-field ${form.attentionRole ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardAttentionRoleOptions.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-ink/55">
            用来标记这段在内容节奏中的职责，例如反转、高潮、章节或信息证明。
          </p>
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">镜头描述</span>
          <input
            value={form.shotDescription}
            onChange={(event) => setForm({ ...form, shotDescription: event.target.value })}
            className="input-field"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">节奏说明</span>
          <input
            value={form.rhythm}
            onChange={(event) => setForm({ ...form, rhythm: event.target.value })}
            className="input-field"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">节拍模式</span>
          <select
            value={form.beatMode}
            onChange={(event) => setForm({ ...form, beatMode: event.target.value })}
            className={`input-field ${beatModeEnabled ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardBeatModeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={beatModeEnabled ? "badge" : "stat-pill"}>
              {beatModeEnabled ? "已设置节拍模式" : "当前不启用节拍"}
            </span>
            <p className="text-xs text-ink/55">节拍模式为可选项，关闭节拍后也可以先保存。</p>
          </div>
        </label>

        {form.selectionTrace ? (
          <div className="rounded-3xl border border-pine/10 bg-mist/60 px-4 py-3 md:col-span-2">
            <p className="text-sm font-semibold text-pine">算法追溯</p>
            <p className="mt-2 text-sm leading-6 text-ink/65">{form.selectionTrace}</p>
          </div>
        ) : null}

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">视觉强度</span>
          <select
            value={form.visualStrength}
            onChange={(event) => setForm({ ...form, visualStrength: event.target.value })}
            className={`input-field ${form.visualStrength ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardVisualStrengthOptions.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">镜头动效策略</span>
          <select
            value={form.motionPolicy}
            onChange={(event) => setForm({ ...form, motionPolicy: event.target.value })}
            className={`input-field ${form.motionPolicy ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardMotionPolicyOptions.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">转场策略</span>
          <select
            value={form.transitionPolicy}
            onChange={(event) => setForm({ ...form, transitionPolicy: event.target.value })}
            className={`input-field ${form.transitionPolicy ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardTransitionPolicyOptions.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">字幕策略</span>
          <select
            value={form.subtitlePolicy}
            onChange={(event) => setForm({ ...form, subtitlePolicy: event.target.value })}
            className={`input-field ${form.subtitlePolicy ? "text-ink" : "text-ink/45"}`}
          >
            {storyboardSubtitlePolicyOptions.map((option) => (
              <option key={option.value || "auto"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <div className="md:col-span-2">
          <p className="text-xs text-ink/55">
            自动模式会按叙事角色突出钩子和高潮、弱化缓冲镜头；也可以为当前镜头单独指定样式。
          </p>
        </div>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">字幕建议</span>
          <input
            value={form.subtitle}
            onChange={(event) => setForm({ ...form, subtitle: event.target.value })}
            className="input-field"
          />
        </label>

        <div className="rounded-3xl border border-pine/10 bg-sand/30 p-4 md:col-span-2">
          <div className="mb-4">
            <h3 className="text-base font-semibold text-ink">口播预留</h3>
            <p className="mt-1 text-xs leading-5 text-ink/55">
              这里先保存口播脚本和时间策略，后续接入 TTS 后可直接生成旁白音轨。
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="block md:col-span-2">
              <span className="mb-2 block text-sm text-ink/75">口播文案</span>
              <textarea
                rows={3}
                value={form.voiceoverText}
                onChange={(event) => setForm({ ...form, voiceoverText: event.target.value })}
                placeholder="可选，默认可沿用字幕；也可以写更适合朗读的完整句子。"
                className="input-field"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm text-ink/75">口播角色</span>
              <select
                value={form.voiceoverRole}
                onChange={(event) => setForm({ ...form, voiceoverRole: event.target.value })}
                className={`input-field ${form.voiceoverRole ? "text-ink" : "text-ink/45"}`}
              >
                {storyboardVoiceoverRoleOptions.map((option) => (
                  <option key={option.value || "none"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-2 block text-sm text-ink/75">口播时间策略</span>
              <select
                value={form.voiceoverTiming}
                onChange={(event) => setForm({ ...form, voiceoverTiming: event.target.value })}
                className={`input-field ${form.voiceoverTiming ? "text-ink" : "text-ink/45"}`}
              >
                {storyboardVoiceoverTimingOptions.map((option) => (
                  <option key={option.value || "none"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">当前镜头节拍点（秒）</span>
          <textarea
            rows={4}
            value={beatPointsText}
            onChange={(event) => setBeatPointsText(event.target.value)}
            className="input-field"
          />
        </label>

        <InlineErrorBanner className="md:col-span-2" message={error} />

        <div className="flex flex-wrap gap-3 md:col-span-2">
          <button type="submit" disabled={isPending} className="btn-primary">
            {isPending
              ? "保存中..."
              : mode === "create"
                ? "新增并返回列表"
                : "保存并返回列表"}
          </button>
          <Link href={backHref} className="btn-secondary">
            返回分镜列表
          </Link>
          <span className="self-center text-xs text-ink/45">Esc 返回列表</span>
        </div>
      </form>
    </>
  );
}
