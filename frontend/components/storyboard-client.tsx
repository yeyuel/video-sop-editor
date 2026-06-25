"use client";

import type { FormEvent } from "react";
import { useEffect, useState, useTransition } from "react";
import { generateStoryboard, saveStoryboard } from "@/lib/browser-api";
import type { StoryboardBundle, StoryboardSegment } from "@/types/domain";

type StoryboardClientProps = {
  projectId: string;
  initialBundle: StoryboardBundle;
  selectedThemeId: string;
  targetDurationSec: number;
  beatMode: string;
  selectedTrackName: string;
};

type SegmentTimeDraft = {
  endTime: string;
  startTime: string;
};

function buildTimeDrafts(segments: StoryboardSegment[]) {
  return Object.fromEntries(
    segments.map((segment) => [
      segment.id,
      {
        startTime: segment.startTime.toString(),
        endTime: segment.endTime.toString()
      }
    ])
  ) as Record<string, SegmentTimeDraft>;
}

export function StoryboardClient({
  projectId,
  initialBundle,
  selectedThemeId,
  targetDurationSec,
  beatMode,
  selectedTrackName
}: StoryboardClientProps) {
  const [bundle, setBundle] = useState(initialBundle);
  const [timeDrafts, setTimeDrafts] = useState<Record<string, SegmentTimeDraft>>(() =>
    buildTimeDrafts(initialBundle.segments)
  );
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  useEffect(() => {
    setTimeDrafts(buildTimeDrafts(bundle.segments));
  }, [bundle.segments]);

  function updateSegment(id: string, patch: Partial<StoryboardSegment>) {
    setBundle((current) => ({
      ...current,
      segments: current.segments.map((segment) =>
        segment.id === id ? { ...segment, ...patch } : segment
      )
    }));
  }

  function updateTimeDraft(
    segmentId: string,
    field: keyof SegmentTimeDraft,
    rawValue: string,
    fallbackValue: number
  ) {
    if (rawValue !== "" && !/^\d*\.?\d*$/.test(rawValue)) {
      return;
    }

    setTimeDrafts((current) => ({
      ...current,
      [segmentId]: {
        startTime: current[segmentId]?.startTime ?? fallbackValue.toString(),
        endTime: current[segmentId]?.endTime ?? fallbackValue.toString(),
        [field]: rawValue
      }
    }));

    if (!rawValue.trim()) {
      return;
    }

    const parsedValue = Number(rawValue);
    if (Number.isNaN(parsedValue)) {
      return;
    }

    updateSegment(segmentId, {
      [field]: parsedValue
    } as Partial<StoryboardSegment>);
  }

  function resetTimeDraft(segmentId: string, field: keyof SegmentTimeDraft, fallbackValue: number) {
    setTimeDrafts((current) => ({
      ...current,
      [segmentId]: {
        startTime: current[segmentId]?.startTime ?? fallbackValue.toString(),
        endTime: current[segmentId]?.endTime ?? fallbackValue.toString(),
        [field]: fallbackValue.toString()
      }
    }));
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
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "生成分镜失败，请稍后重试。"
        );
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        const nextBundle = await saveStoryboard(projectId, {
          themeId: selectedThemeId,
          segments: bundle.segments
        });
        setBundle(nextBundle);
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "保存分镜失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isPending}
          className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "生成中..." : "根据节拍生成分镜"}
        </button>
        <button
          type="submit"
          disabled={isPending || bundle.segments.length === 0}
          className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "保存中..." : "保存分镜"}
        </button>
      </div>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
          绑定素材：{bundle.validation.allSegmentsBoundToAsset ? "通过" : "未通过"}
        </div>
        <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
          地点连续性：
          {bundle.validation.locationOrderValidationEnabled
            ? bundle.validation.locationContinuityPassed
              ? "通过"
              : "未通过"
            : "未启用"}
        </div>
        <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
          节拍对齐：{bundle.validation.beatAlignmentPassed ? "通过" : "未通过"}
        </div>
        <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
          总时长：{bundle.validation.totalDurationSec}s
        </div>
      </div>

      {bundle.segments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-pine/20 bg-white px-4 py-8 text-center text-sm text-ink/60">
          还没有分镜时间线。请先完成主题选择和节奏规划，再点击上方按钮生成。
        </div>
      ) : (
        <div className="space-y-4">
          {bundle.segments.map((segment) => (
            <article
              key={segment.id}
              className="rounded-xl2 border border-black/5 bg-white/90 p-5 shadow-card"
            >
              <div className="grid gap-4 md:grid-cols-4">
                <label className="block">
                  <span className="mb-2 block text-sm text-ink/75">开始</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={timeDrafts[segment.id]?.startTime ?? segment.startTime.toString()}
                    onChange={(event) =>
                      updateTimeDraft(
                        segment.id,
                        "startTime",
                        event.target.value,
                        segment.startTime
                      )
                    }
                    onBlur={() => {
                      if (!(timeDrafts[segment.id]?.startTime ?? "").trim()) {
                        resetTimeDraft(segment.id, "startTime", segment.startTime);
                      }
                    }}
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-ink/75">结束</span>
                  <input
                    type="text"
                    inputMode="decimal"
                    value={timeDrafts[segment.id]?.endTime ?? segment.endTime.toString()}
                    onChange={(event) =>
                      updateTimeDraft(segment.id, "endTime", event.target.value, segment.endTime)
                    }
                    onBlur={() => {
                      if (!(timeDrafts[segment.id]?.endTime ?? "").trim()) {
                        resetTimeDraft(segment.id, "endTime", segment.endTime);
                      }
                    }}
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-ink/75">素材 ID</span>
                  <input
                    value={segment.assetId}
                    onChange={(event) =>
                      updateSegment(segment.id, { assetId: event.target.value })
                    }
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-ink/75">功能标签</span>
                  <input
                    value={segment.function}
                    onChange={(event) =>
                      updateSegment(segment.id, { function: event.target.value })
                    }
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block md:col-span-2">
                  <span className="mb-2 block text-sm text-ink/75">镜头描述</span>
                  <input
                    value={segment.shotDescription}
                    onChange={(event) =>
                      updateSegment(segment.id, { shotDescription: event.target.value })
                    }
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-ink/75">节奏说明</span>
                  <input
                    value={segment.rhythm}
                    onChange={(event) =>
                      updateSegment(segment.id, { rhythm: event.target.value })
                    }
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-ink/75">节拍模式</span>
                  <input
                    value={segment.beatMode}
                    onChange={(event) =>
                      updateSegment(segment.id, { beatMode: event.target.value })
                    }
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <label className="block md:col-span-4">
                  <span className="mb-2 block text-sm text-ink/75">字幕建议</span>
                  <input
                    value={segment.subtitle}
                    onChange={(event) =>
                      updateSegment(segment.id, { subtitle: event.target.value })
                    }
                    className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
                  />
                </label>
                <div className="rounded-2xl bg-sand/55 px-4 py-3 text-sm text-ink/70 md:col-span-4">
                  当前段节拍点：{segment.beatPoints.join(", ") || "无"}
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </form>
  );
}
