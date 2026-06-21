"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent, KeyboardEvent } from "react";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { BlockingNotice } from "@/components/async-status";
import { insertStoryboardSegment, updateStoryboardSegment } from "@/lib/browser-api";
import {
  storyboardBeatModeOptions,
  storyboardFunctionOptions
} from "@/lib/storyboard-options";
import type { Asset, StoryboardSegment } from "@/types/domain";

type StoryboardSegmentEditorClientProps = {
  afterSegmentId?: string;
  assets: Asset[];
  backHref: string;
  mode?: "create" | "edit";
  projectId: string;
  segment: StoryboardSegment;
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

function highlightText(text: string, query: string) {
  const normalizedQuery = query.trim();
  if (!normalizedQuery) {
    return text;
  }

  const lowerText = text.toLowerCase();
  const lowerQuery = normalizedQuery.toLowerCase();
  const startIndex = lowerText.indexOf(lowerQuery);
  if (startIndex === -1) {
    return text;
  }

  const endIndex = startIndex + normalizedQuery.length;
  return (
    <>
      {text.slice(0, startIndex)}
      <mark className="rounded bg-[#f6e7bc] px-1 text-ink">{text.slice(startIndex, endIndex)}</mark>
      {text.slice(endIndex)}
    </>
  );
}

export function StoryboardSegmentEditorClient({
  afterSegmentId,
  assets,
  backHref,
  mode = "edit",
  projectId,
  segment,
  themeId
}: StoryboardSegmentEditorClientProps) {
  const router = useRouter();
  const [form, setForm] = useState(segment);
  const [startTimeText, setStartTimeText] = useState(segment.startTime.toString());
  const [endTimeText, setEndTimeText] = useState(segment.endTime.toString());
  const [beatPointsText, setBeatPointsText] = useState(numberListToText(segment.beatPoints));
  const [assetQuery, setAssetQuery] = useState(segment.assetId);
  const [locationFilter, setLocationFilter] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();
  const assetItemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const locationOptions = useMemo(
    () => Array.from(new Set(assets.map((asset) => asset.location).filter(Boolean))).sort(),
    [assets]
  );

  const assetMatches = useMemo(() => {
    const query = assetQuery.trim().toLowerCase();
    const scopedAssets = locationFilter
      ? assets.filter((asset) => asset.location === locationFilter)
      : assets;

    if (!query) {
      return scopedAssets.slice(0, 12);
    }

    return scopedAssets
      .filter((asset) => {
        const haystack = `${asset.assetId} ${asset.scene} ${asset.location}`.toLowerCase();
        return haystack.includes(query);
      })
      .slice(0, 12);
  }, [assetQuery, assets, locationFilter]);

  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.assetId === form.assetId),
    [assets, form.assetId]
  );
  const beatModeEnabled = form.beatMode && form.beatMode !== "none";

  useEffect(() => {
    setHighlightedIndex(0);
  }, [assetQuery]);

  useEffect(() => {
    const activeItem = assetItemRefs.current[highlightedIndex];
    activeItem?.scrollIntoView({
      block: "nearest",
      behavior: "smooth"
    });
  }, [highlightedIndex]);

  function selectAsset(asset: Asset) {
    setForm({ ...form, assetId: asset.assetId });
    setAssetQuery(asset.assetId);
  }

  function clearSelectedAsset() {
    setForm({ ...form, assetId: "" });
    setAssetQuery("");
    setHighlightedIndex(0);
  }

  function handleAssetKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      const nextAsset = assetMatches[highlightedIndex] ?? assetMatches[0];
      if (nextAsset) {
        selectAsset(nextAsset);
      }
      return;
    }

    if (assetMatches.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.min(current + 1, assetMatches.length - 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((current) => Math.max(current - 1, 0));
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setHighlightedIndex(0);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    startTransition(async () => {
      try {
        const startTime = Number(startTimeText);
        const endTime = Number(endTimeText);
        if (!startTimeText.trim() || Number.isNaN(startTime)) {
          throw new Error("请填写有效的开始时间。");
        }
        if (!endTimeText.trim() || Number.isNaN(endTime)) {
          throw new Error("请填写有效的结束时间。");
        }

        const payload = {
          ...form,
          startTime,
          endTime,
          beatPoints: parseNumberList(beatPointsText)
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
        setError(
          submitError instanceof Error ? submitError.message : "保存镜头失败，请稍后再试。"
        );
      }
    });
  }

  return (
    <>
      <BlockingNotice
        visible={isPending}
        title={mode === "create" ? "正在新增镜头" : "正在保存镜头"}
        description="保存后会自动返回分镜列表，请稍等片刻。"
      />

      <form className="grid gap-5 md:grid-cols-2" onSubmit={handleSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">开始（秒）</span>
          <input
            type="text"
            inputMode="decimal"
            value={startTimeText}
            onChange={(event) => {
              const nextValue = event.target.value;
              if (nextValue === "" || /^\d*\.?\d*$/.test(nextValue)) {
                setStartTimeText(nextValue);
              }
            }}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">结束（秒）</span>
          <input
            type="text"
            inputMode="decimal"
            value={endTimeText}
            onChange={(event) => {
              const nextValue = event.target.value;
              if (nextValue === "" || /^\d*\.?\d*$/.test(nextValue)) {
                setEndTimeText(nextValue);
              }
            }}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        <div className="block">
          <span className="mb-2 block text-sm text-ink/75">素材</span>
          <div className="mb-3 grid gap-3 sm:grid-cols-[0.8fr_1.2fr]">
            <div className="block">
              <span className="mb-2 block text-xs text-ink/55">地点筛选</span>
              <select
                value={locationFilter}
                onChange={(event) => {
                  setLocationFilter(event.target.value);
                  setHighlightedIndex(0);
                }}
                className={`w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine ${
                  locationFilter ? "text-ink" : "text-ink/45"
                }`}
              >
                <option value="">全部地点</option>
                {locationOptions.map((location) => (
                  <option key={location} value={location}>
                    {location}
                  </option>
                ))}
              </select>
            </div>
            <div className="block">
              <span className="mb-2 block text-xs text-ink/55">搜索素材</span>
              <input
                value={assetQuery}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  setAssetQuery(nextValue);
                  if (!nextValue.trim()) {
                    setForm({ ...form, assetId: "" });
                  }
                }}
                onKeyDown={handleAssetKeyDown}
                placeholder="搜索素材 ID 或素材描述"
                className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
              />
            </div>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ink/55">
            <span>{locationFilter ? `当前地点：${locationFilter}` : "当前地点：全部"}</span>
            <span>支持搜索素材 ID / 地点 / 描述</span>
            <span>↑ / ↓ 选择</span>
            <span>Enter 确认</span>
            <span>Esc 取消高亮</span>
          </div>
          {selectedAsset ? (
            <div className="mt-3 rounded-2xl border border-pine/15 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">{selectedAsset.assetId}</p>
                  <p className="mt-1 text-sm leading-6 text-ink/65">
                    {selectedAsset.location} / {selectedAsset.scene}
                  </p>
                  <p className="mt-1 text-xs text-ink/50">
                    {selectedAsset.relativePath || "当前素材未填写相对路径"}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`/projects/${projectId}/assets/${selectedAsset.assetId}/edit`}
                    className="inline-flex rounded-full border border-pine/20 bg-white px-3 py-1.5 text-xs font-medium text-pine transition hover:bg-mist"
                  >
                    查看素材详情
                  </Link>
                  <button
                    type="button"
                    onClick={clearSelectedAsset}
                    className="inline-flex rounded-full border border-clay/20 bg-white px-3 py-1.5 text-xs font-medium text-clay transition hover:bg-[#fff4ee]"
                  >
                    清空已选
                  </button>
                </div>
              </div>
            </div>
          ) : null}
          <div className="mt-3 max-h-80 space-y-2 overflow-y-auto rounded-2xl border border-pine/10 bg-mist/55 p-3">
            {assetMatches.length === 0 ? (
              <p className="text-sm text-ink/55">没有匹配到素材，可以留空后继续保存。</p>
            ) : (
              assetMatches.map((asset) => {
                const matchIndex = assetMatches.indexOf(asset);
                const isActive = asset.assetId === form.assetId;
                const isHighlighted =
                  asset.assetId !== form.assetId &&
                  assetMatches[highlightedIndex]?.assetId === asset.assetId;
                return (
                  <button
                    key={asset.assetId}
                    ref={(element) => {
                      assetItemRefs.current[matchIndex] = element;
                    }}
                    type="button"
                    onClick={() => selectAsset(asset)}
                    onMouseEnter={() => setHighlightedIndex(matchIndex)}
                    className={`flex w-full items-start justify-between rounded-2xl px-3 py-3 text-left transition ${
                      isActive
                        ? "bg-white shadow-sm ring-1 ring-pine/15"
                        : isHighlighted
                          ? "bg-white/85"
                          : "hover:bg-white/70"
                    }`}
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ink">
                        {highlightText(asset.assetId, assetQuery)}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-ink/60">
                        {highlightText(`${asset.location} / ${asset.scene}`, assetQuery)}
                      </p>
                    </div>
                    {isActive ? (
                      <span className="ml-3 rounded-full bg-pine px-2 py-1 text-xs text-white">
                        已选
                      </span>
                    ) : isHighlighted ? (
                      <span className="ml-3 rounded-full bg-sand px-2 py-1 text-xs text-ink/70">
                        回车选择
                      </span>
                    ) : null}
                  </button>
                );
              })
            )}
          </div>
          {!selectedAsset ? (
            <p className="mt-2 text-xs text-ink/55">当前未绑定素材，允许先保存后补充。</p>
          ) : null}
        </div>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">功能标签</span>
          <select
            value={form.function}
            onChange={(event) => setForm({ ...form, function: event.target.value })}
            className={`w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine ${
              form.function ? "text-ink" : "text-ink/45"
            }`}
          >
            {storyboardFunctionOptions.map((option) => (
              <option key={option.value || "none"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-1 text-xs ${
                form.function
                  ? "bg-mist text-ink/70"
                  : "bg-sand text-ink/50 ring-1 ring-inset ring-pine/10"
              }`}
            >
              {form.function ? "已设置功能标签" : "当前未设置"}
            </span>
            <p className="text-xs text-ink/55">功能标签为可选项，先不标注也可以保存。</p>
          </div>
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">镜头描述</span>
          <input
            value={form.shotDescription}
            onChange={(event) => setForm({ ...form, shotDescription: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">节奏说明</span>
          <input
            value={form.rhythm}
            onChange={(event) => setForm({ ...form, rhythm: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">节拍模式</span>
          <select
            value={form.beatMode}
            onChange={(event) => setForm({ ...form, beatMode: event.target.value })}
            className={`w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine ${
              beatModeEnabled ? "text-ink" : "text-ink/45"
            }`}
          >
            {storyboardBeatModeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-1 text-xs ${
                beatModeEnabled
                  ? "bg-mist text-ink/70"
                  : "bg-sand text-ink/50 ring-1 ring-inset ring-pine/10"
              }`}
            >
              {beatModeEnabled ? "已设置节拍模式" : "当前不启用节拍"}
            </span>
            <p className="text-xs text-ink/55">节拍模式为可选项，关闭节拍后也可以先保存。</p>
          </div>
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">字幕建议</span>
          <input
            value={form.subtitle}
            onChange={(event) => setForm({ ...form, subtitle: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">当前镜头节拍点（秒）</span>
          <textarea
            rows={4}
            value={beatPointsText}
            onChange={(event) => setBeatPointsText(event.target.value)}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>

        {error ? (
          <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay md:col-span-2">
            {error}
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3 md:col-span-2">
          <button
            type="submit"
            disabled={isPending}
            className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending
              ? "保存中..."
              : mode === "create"
                ? "新增并返回列表"
                : "保存并返回列表"}
          </button>
          <Link
            href={backHref}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist"
          >
            返回分镜列表
          </Link>
        </div>
      </form>
    </>
  );
}
