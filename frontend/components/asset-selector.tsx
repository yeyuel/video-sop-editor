"use client";

import Link from "next/link";
import type { KeyboardEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset } from "@/types/domain";

type AssetSelectorProps = {
  assets: Asset[];
  onChange: (assetId: string) => void;
  projectId: string;
  value: string;
};

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

function assetMatchesQuery(asset: Asset, query: string) {
  const haystack = `${asset.assetId} ${asset.scene} ${asset.location}`.toLowerCase();
  return haystack.includes(query);
}

export function AssetSelector({ assets, onChange, projectId, value }: AssetSelectorProps) {
  const [assetQuery, setAssetQuery] = useState(value);
  const [locationFilter, setLocationFilter] = useState("");
  const [highlightedAssetId, setHighlightedAssetId] = useState("");
  const assetItemRefs = useRef<Record<string, HTMLButtonElement | null>>({});

  const locationOptions = useMemo(
    () => Array.from(new Set(assets.map((asset) => asset.location).filter(Boolean))).sort(),
    [assets]
  );

  const filteredAssets = useMemo(() => {
    const query = assetQuery.trim().toLowerCase();
    const scopedAssets = locationFilter
      ? assets.filter((asset) => asset.location === locationFilter)
      : assets;

    if (!query) {
      return scopedAssets;
    }

    return scopedAssets.filter((asset) => assetMatchesQuery(asset, query));
  }, [assetQuery, assets, locationFilter]);

  const groupedAssets = useMemo(() => {
    const groups = new Map<string, Asset[]>();
    for (const asset of filteredAssets) {
      const location = asset.location || "未填写地点";
      const current = groups.get(location) ?? [];
      current.push(asset);
      groups.set(location, current);
    }

    return Array.from(groups.entries()).sort(([left], [right]) => left.localeCompare(right, "zh-CN"));
  }, [filteredAssets]);

  const flatAssets = useMemo(
    () => groupedAssets.flatMap(([, groupAssets]) => groupAssets),
    [groupedAssets]
  );

  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.assetId === value),
    [assets, value]
  );

  useEffect(() => {
    if (!flatAssets.length) {
      setHighlightedAssetId("");
      return;
    }

    if (!highlightedAssetId || !flatAssets.some((asset) => asset.assetId === highlightedAssetId)) {
      setHighlightedAssetId(flatAssets[0].assetId);
    }
  }, [flatAssets, highlightedAssetId]);

  useEffect(() => {
    const activeItem = highlightedAssetId ? assetItemRefs.current[highlightedAssetId] : null;
    activeItem?.scrollIntoView({
      block: "nearest",
      behavior: "smooth"
    });
  }, [highlightedAssetId]);

  function selectAsset(asset: Asset) {
    onChange(asset.assetId);
    setAssetQuery(asset.assetId);
  }

  function clearSelectedAsset() {
    onChange("");
    setAssetQuery("");
    setHighlightedAssetId(flatAssets[0]?.assetId ?? "");
  }

  function handleAssetKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      const nextAsset =
        flatAssets.find((asset) => asset.assetId === highlightedAssetId) ?? flatAssets[0];
      if (nextAsset) {
        selectAsset(nextAsset);
      }
      return;
    }

    if (!flatAssets.length) {
      return;
    }

    const currentIndex = flatAssets.findIndex((asset) => asset.assetId === highlightedAssetId);

    if (event.key === "ArrowDown") {
      event.preventDefault();
      const nextIndex = Math.min(currentIndex + 1, flatAssets.length - 1);
      setHighlightedAssetId(flatAssets[nextIndex]?.assetId ?? "");
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      const nextIndex = Math.max(currentIndex - 1, 0);
      setHighlightedAssetId(flatAssets[nextIndex]?.assetId ?? "");
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setHighlightedAssetId(flatAssets[0]?.assetId ?? "");
    }
  }

  return (
    <div className="block">
      <span className="mb-2 block text-sm text-ink/75">素材</span>
      <div className="mb-3 grid gap-3 sm:grid-cols-[0.8fr_1.2fr]">
        <div className="block">
          <span className="mb-2 block text-xs text-ink/55">地点筛选</span>
          <select
            value={locationFilter}
            onChange={(event) => {
              setLocationFilter(event.target.value);
              setHighlightedAssetId("");
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
                onChange("");
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
        <span>按地点分组展示</span>
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

      <div className="mt-3 max-h-80 space-y-4 overflow-y-auto rounded-2xl border border-pine/10 bg-mist/55 p-3">
        {groupedAssets.length === 0 ? (
          <p className="text-sm text-ink/55">没有匹配到素材，可以留空后继续保存。</p>
        ) : (
          groupedAssets.map(([location, groupAssets]) => (
            <section key={location}>
              <div className="sticky top-0 z-10 mb-2 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-pine shadow-sm">
                {location}
                <span className="ml-2 text-ink/45">{groupAssets.length} 条</span>
              </div>
              <div className="space-y-2">
                {groupAssets.map((asset) => {
                  const isActive = asset.assetId === value;
                  const isHighlighted =
                    asset.assetId !== value && highlightedAssetId === asset.assetId;

                  return (
                    <button
                      key={asset.assetId}
                      ref={(element) => {
                        assetItemRefs.current[asset.assetId] = element;
                      }}
                      type="button"
                      onClick={() => selectAsset(asset)}
                      onMouseEnter={() => setHighlightedAssetId(asset.assetId)}
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
                          {highlightText(asset.scene, assetQuery)}
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
                })}
              </div>
            </section>
          ))
        )}
      </div>
      {!selectedAsset ? (
        <p className="mt-2 text-xs text-ink/55">当前未绑定素材，允许先保存后补充。</p>
      ) : null}
    </div>
  );
}
