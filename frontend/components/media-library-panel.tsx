"use client";

import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";

import {
  ChevronIcon,
  FileKindIcon,
  SearchIcon
} from "@/components/media-tree-icons";
import { InlineErrorBanner } from "@/components/ui-primitives";
import { scanMediaLibrary, type MediaLibraryNode, type MediaLibraryScanResult } from "@/lib/browser-api";
import { mediaKindLabel } from "@/lib/media-preview-utils";
import {
  collectMediaFiles,
  findNextUnrecordedFile,
  patchScanResultHasAsset
} from "@/lib/media-library-tree-utils";
import {
  clearMediaLibrarySession,
  isMediaLibrarySessionValid,
  loadMediaLibrarySession,
  saveMediaLibrarySession
} from "@/lib/media-library-session";

type MediaLibraryPanelProps = {
  projectId: string;
  mediaRoot: string;
  selectedPath?: string;
  onSelectFile: (file: MediaLibraryNode) => void;
  /** 保存素材后递增，触发后台重新扫描并更新「已录入」标记。 */
  rescanToken?: number;
  /** 与 rescanToken 配合：录入完成后从该路径跳下一条未录入文件。 */
  advanceFromPath?: string | null;
  onAdvanceComplete?: () => void;
};

function formatSize(sizeBytes?: number) {
  if (!sizeBytes || sizeBytes <= 0) {
    return "";
  }
  if (sizeBytes < 1024 * 1024) {
    return `${(sizeBytes / 1024).toFixed(1)} KB`;
  }
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function filterTree(node: MediaLibraryNode, query: string): MediaLibraryNode | null {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return node;
  }

  if (node.nodeType === "file") {
    const haystack = `${node.name} ${node.relativePath}`.toLowerCase();
    return haystack.includes(normalized) ? node : null;
  }

  const children = (node.children ?? [])
    .map((child) => filterTree(child, normalized))
    .filter((child): child is MediaLibraryNode => child !== null);

  if (children.length > 0 || node.name.toLowerCase().includes(normalized)) {
    return { ...node, children };
  }

  return null;
}

function collectDirectoryPaths(node: MediaLibraryNode, paths: string[] = []) {
  if (node.nodeType === "directory") {
    paths.push(node.relativePath);
    node.children?.forEach((child) => collectDirectoryPaths(child, paths));
  }
  return paths;
}

function TreeNode({
  node,
  depth,
  expanded,
  onToggle,
  selectedPath,
  onSelectFile,
  isLastSibling
}: {
  node: MediaLibraryNode;
  depth: number;
  expanded: Record<string, boolean>;
  onToggle: (path: string) => void;
  selectedPath?: string;
  onSelectFile: (file: MediaLibraryNode) => void;
  isLastSibling?: boolean;
}) {
  const isDirectory = node.nodeType === "directory";
  const isOpen = expanded[node.relativePath] ?? depth < 2;
  const isSelected = !isDirectory && node.relativePath === selectedPath;
  const indent = depth * 16;

  if (isDirectory) {
    return (
      <div className="relative">
        {depth > 0 ? (
          <span
            aria-hidden
            className="pointer-events-none absolute top-0 w-px bg-gradient-to-b from-pine/12 to-pine/6"
            style={{ left: `${indent - 6}px`, bottom: isLastSibling ? "50%" : 0 }}
          />
        ) : null}
        <button
          type="button"
          onClick={() => onToggle(node.relativePath)}
          className={clsx(
            "group relative flex w-full items-center gap-2 rounded-xl py-2 pr-2 text-left text-[13px] transition",
            "hover:bg-pine/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pine/20"
          )}
          style={{ paddingLeft: `${indent + 8}px` }}
        >
          <ChevronIcon open={isOpen} />
          <FileKindIcon isDirectory open={isOpen} />
          <span className="truncate font-medium text-ink/85 group-hover:text-ink">{node.name}</span>
          <span className="ml-auto shrink-0 rounded-md bg-sand/80 px-1.5 py-0.5 text-[10px] font-medium text-ink/40">
            {(node.children ?? []).length}
          </span>
        </button>
        {isOpen ? (
          <div className="relative">
            {(node.children ?? []).map((child, index) => (
              <TreeNode
                key={`${child.nodeType}:${child.relativePath || child.name}`}
                node={child}
                depth={depth + 1}
                expanded={expanded}
                onToggle={onToggle}
                selectedPath={selectedPath}
                onSelectFile={onSelectFile}
                isLastSibling={index === (node.children ?? []).length - 1}
              />
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="relative">
      {depth > 0 ? (
        <span
          aria-hidden
          className="pointer-events-none absolute top-0 w-px bg-pine/10"
          style={{ left: `${indent - 6}px`, bottom: isLastSibling ? "50%" : 0 }}
        />
      ) : null}
      <button
        type="button"
        onClick={() => onSelectFile(node)}
        className={clsx(
          "group relative flex w-full items-center gap-2 rounded-xl py-2 pr-2 text-left text-[13px] transition",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-pine/20",
          isSelected
            ? "bg-pine/[0.08] text-ink shadow-[inset_2px_0_0_0_#31584f]"
            : "text-ink/75 hover:bg-pine/[0.04] hover:text-ink"
        )}
        style={{ paddingLeft: `${indent + 28}px` }}
        title={node.relativePath}
      >
        <FileKindIcon kind={node.mediaKind} />
        <span className="min-w-0 flex-1 truncate">{node.name}</span>
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {node.hasAsset ? (
            <span
              className={clsx(
                "rounded-md px-1.5 py-0.5 text-[10px] font-medium",
                isSelected ? "bg-pine/15 text-pine" : "bg-mist/80 text-pine/80"
              )}
            >
              已录入
            </span>
          ) : null}
          <span
            className={clsx(
              "rounded-md px-1.5 py-0.5 text-[10px] tabular-nums",
              isSelected ? "bg-white/70 text-ink/50" : "bg-sand/70 text-ink/40"
            )}
          >
            {mediaKindLabel(node.mediaKind, "short")}
          </span>
          {formatSize(node.sizeBytes) ? (
            <span className="hidden min-w-[3.5rem] text-right text-[10px] tabular-nums text-ink/35 sm:inline">
              {formatSize(node.sizeBytes)}
            </span>
          ) : null}
        </div>
      </button>
    </div>
  );
}

function TreeSkeleton() {
  return (
    <div className="space-y-2 px-2 py-3">
      {Array.from({ length: 8 }).map((_, index) => (
        <div
          key={index}
          className="h-9 animate-pulse rounded-xl bg-gradient-to-r from-sand/80 via-white to-sand/80"
          style={{ marginLeft: `${(index % 3) * 16}px`, width: `${88 - (index % 3) * 8}%` }}
        />
      ))}
    </div>
  );
}

export function MediaLibraryPanel({
  projectId,
  mediaRoot,
  selectedPath,
  onSelectFile,
  rescanToken = 0,
  advanceFromPath = null,
  onAdvanceComplete
}: MediaLibraryPanelProps) {
  const hydratedRef = useRef(false);
  const [scanResult, setScanResult] = useState<MediaLibraryScanResult | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [searchQuery, setSearchQuery] = useState("");
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();
  const [isBackgroundRescan, setIsBackgroundRescan] = useState(false);

  useEffect(() => {
    if (hydratedRef.current) {
      return;
    }
    hydratedRef.current = true;
    const saved = loadMediaLibrarySession(projectId);
    if (saved && isMediaLibrarySessionValid(saved, mediaRoot)) {
      setScanResult(saved.scanResult);
      setExpanded(saved.expanded);
      setSearchQuery(saved.searchQuery);
    } else if (saved) {
      clearMediaLibrarySession(projectId);
      setError("素材根目录已变更或扫描结果已过期，请重新扫描目录。");
    }
  }, [mediaRoot, projectId]);

  useEffect(() => {
    if (!scanResult) {
      return;
    }
    saveMediaLibrarySession(projectId, {
      mediaRoot: scanResult.mediaRoot || mediaRoot,
      scanResult,
      expanded,
      searchQuery,
      updatedAt: Date.now()
    });
  }, [expanded, mediaRoot, projectId, scanResult, searchQuery]);

  const runScan = useCallback(
    (options?: { background?: boolean }) => {
      setError("");
      if (!options?.background) {
        setSearchQuery("");
      }
      const run = async () => {
        if (options?.background) {
          setIsBackgroundRescan(true);
        }
        try {
          const result = await scanMediaLibrary(projectId);
          setScanResult(result);
          if (!options?.background) {
            setExpanded({ "": true });
          }
        } catch (scanError) {
          if (!options?.background) {
            setScanResult(null);
          }
          setError(scanError instanceof Error ? scanError.message : "目录扫描失败。");
        } finally {
          setIsBackgroundRescan(false);
        }
      };

      if (options?.background) {
        void run();
        return;
      }

      startTransition(run);
    },
    [projectId]
  );

  const handleScan = useCallback(() => {
    runScan();
  }, [runScan]);

  const lastRescanTokenRef = useRef(0);
  const advancedPathRef = useRef<string | null>(null);

  useEffect(() => {
    if (!advanceFromPath) {
      advancedPathRef.current = null;
    }
  }, [advanceFromPath]);

  // 录入保存后：标记已录入 + 后台 rescan（不在 setState updater 里更新父组件）
  useEffect(() => {
    if (!rescanToken || rescanToken === lastRescanTokenRef.current) {
      return;
    }
    lastRescanTokenRef.current = rescanToken;

    if (advanceFromPath) {
      setScanResult((current) =>
        current ? patchScanResultHasAsset(current, advanceFromPath) : current
      );
    }

    runScan({ background: true });
  }, [advanceFromPath, rescanToken, runScan]);

  // 树已打上「已录入」后再跳下一条
  useEffect(() => {
    if (!advanceFromPath || !scanResult) {
      return;
    }

    const recorded = collectMediaFiles(scanResult.tree).find(
      (file) => file.relativePath === advanceFromPath
    );
    if (!recorded?.hasAsset) {
      return;
    }
    if (advancedPathRef.current === advanceFromPath) {
      return;
    }
    advancedPathRef.current = advanceFromPath;

    const next = findNextUnrecordedFile(scanResult.tree, advanceFromPath);
    if (next) {
      onSelectFile(next);
    }
    onAdvanceComplete?.();
  }, [advanceFromPath, onAdvanceComplete, onSelectFile, scanResult]);

  const filteredTree = useMemo(() => {
    if (!scanResult?.tree) {
      return null;
    }
    return filterTree(scanResult.tree, searchQuery);
  }, [scanResult?.tree, searchQuery]);

  const summary = useMemo(() => {
    if (!scanResult) {
      return null;
    }
    return {
      files: scanResult.fileCount,
      dirs: scanResult.directoryCount,
      truncated: scanResult.truncated
    };
  }, [scanResult]);

  return (
    <div className="surface-panel flex h-full min-h-[560px] flex-col overflow-hidden">
      <div className="border-b border-line bg-white px-4 pb-4 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-[0.26em] text-pine/70">
              Media Library
            </p>
            <h3 className="mt-1.5 text-lg font-semibold tracking-tight text-ink">素材目录</h3>
          </div>
          {summary ? (
            <div className="flex flex-wrap items-center justify-end gap-1.5">
              <span className="badge">{summary.files} 文件</span>
              <span className="badge">{summary.dirs} 目录</span>
              {isBackgroundRescan ? (
                <span className="badge-ai animate-pulse">同步中…</span>
              ) : null}
            </div>
          ) : null}
        </div>

        <p className="mt-2 line-clamp-2 break-all text-[11px] leading-5 text-ink/45" title={mediaRoot}>
          {mediaRoot || "未配置 mediaRoot"}
        </p>

        <button
          type="button"
          disabled={isPending || !mediaRoot.trim()}
          onClick={handleScan}
          className="btn-primary mt-4 w-full"
        >
          {isPending ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              扫描中…
            </>
          ) : scanResult ? (
            "重新扫描"
          ) : (
            "扫描目录"
          )}
        </button>

        {scanResult ? (
          <div className="relative mt-3">
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/35" />
            <input
              value={searchQuery}
              onChange={(event) => {
                const nextQuery = event.target.value;
                setSearchQuery(nextQuery);
                if (nextQuery.trim() && scanResult.tree) {
                  const paths = collectDirectoryPaths(scanResult.tree);
                  setExpanded((current) => {
                    const next: Record<string, boolean> = { ...current, "": true };
                    paths.forEach((path) => {
                      next[path] = true;
                    });
                    return next;
                  });
                }
              }}
              placeholder="搜索文件名或路径…"
              className="input-field py-2.5 pl-9 pr-3"
            />
          </div>
        ) : null}

        {summary?.truncated ? (
          <p className="mt-2 text-[11px] text-clay/80">目录较大，已截断部分结果。</p>
        ) : null}
      </div>

      <div className="tree-scroll flex-1 overflow-auto px-2 py-2">
        {error ? <InlineErrorBanner className="mx-1 my-2" message={error} /> : null}
        {isPending ? <TreeSkeleton /> : null}
        {!scanResult?.tree && !isPending && !error ? (
          <div className="surface-muted mx-2 my-6 border-dashed px-4 py-10 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/80 shadow-sm">
              <FileKindIcon isDirectory open />
            </div>
            <p className="mt-4 text-sm font-medium text-ink/75">浏览本地素材库</p>
            <p className="mt-2 text-xs leading-6 text-ink/50">
              扫描 mediaRoot 后，可在此按目录选择视频、图片与音频并带入录入表单。
            </p>
          </div>
        ) : null}
        {filteredTree ? (
          <TreeNode
            node={filteredTree}
            depth={0}
            expanded={expanded}
            onToggle={(path) =>
              setExpanded((current) => ({ ...current, [path]: !current[path] }))
            }
            selectedPath={selectedPath}
            onSelectFile={onSelectFile}
          />
        ) : null}
        {scanResult && !isPending && !filteredTree && !error ? (
          <p className="px-3 py-8 text-center text-sm text-ink/50">没有匹配的媒体文件。</p>
        ) : null}
      </div>
    </div>
  );
}
