"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { EmptyState, InlineErrorBanner } from "@/components/ui-primitives";
import { generateThemes, generateThemesWithLlm, selectTheme } from "@/lib/browser-api";
import {
  applyLlmProgressEvent,
  createLlmProgressState,
  THEME_LLM_STAGES,
  type LlmProgressViewState
} from "@/lib/llm-progress-stages";
import { describeLlmStatus, llmNoticeTone } from "@/lib/llm-status";
import type { NarrativeTheme } from "@/types/domain";

type ThemeSelectorClientProps = {
  projectId: string;
  initialThemes: NarrativeTheme[];
};

function ThemeCard({
  disabled,
  onSelect,
  theme
}: {
  disabled: boolean;
  onSelect: (themeId: string) => void;
  theme: NarrativeTheme;
}) {
  const isSelected = theme.isSelected;

  return (
    <article
      className={[
        "rounded-xl2 border p-5 shadow-card transition",
        isSelected
          ? "border-pine bg-mist ring-2 ring-pine/15"
          : "border-black/5 bg-white/90 hover:border-pine/25"
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold text-ink">{theme.title}</h3>
        <span
          className={[
            "rounded-full px-3 py-1 text-xs",
            isSelected ? "bg-pine text-white" : "bg-white/85 text-pine"
          ].join(" ")}
        >
          {isSelected ? "当前已选" : theme.coreEmotion}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-ink/70">{theme.summary}</p>
      <div className="mt-4 space-y-2 text-sm text-ink/70">
        <p>预期节奏：{theme.rhythmProfile}</p>
        <p>平台理由：{theme.platformReason}</p>
        {theme.usedLocations.length > 0 ? (
          <p>主要地点：{theme.usedLocations.join("、")}</p>
        ) : null}
        {theme.usedAssetIds.length > 0 ? (
          <p>参考素材：{theme.usedAssetIds.join("、")}</p>
        ) : null}
      </div>
      <button
        type="button"
        onClick={() => onSelect(theme.id)}
        disabled={disabled || isSelected}
        className={[
          "mt-5 inline-flex rounded-full px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
          isSelected
            ? "border border-pine/20 bg-white text-pine"
            : "bg-pine text-white hover:bg-pine/90"
        ].join(" ")}
      >
        {isSelected ? "当前已选主题" : "设为当前主题"}
      </button>
    </article>
  );
}

export function ThemeSelectorClient({
  projectId,
  initialThemes
}: ThemeSelectorClientProps) {
  const router = useRouter();
  const [themes, setThemes] = useState(initialThemes);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [isPending, startTransition] = useTransition();
  const [llmProgress, setLlmProgress] = useState<LlmProgressViewState | null>(null);

  const selectedTheme = useMemo(
    () => themes.find((theme) => theme.isSelected),
    [themes]
  );
  const candidateThemes = useMemo(
    () => themes.filter((theme) => !theme.isSelected),
    [themes]
  );

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

  function handleGenerate() {
    setError("");
    startTransition(async () => {
      try {
        const nextThemes = await generateThemes(projectId, 3);
        setThemes(nextThemes);
        router.refresh();
        setNotice({ title: "主题已生成", message: "已基于当前项目和素材生成候选主题。" });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成主题失败，请稍后重试。"
        );
      }
    });
  }

  function handleSelect(themeId: string) {
    setError("");
    startTransition(async () => {
      try {
        const nextThemes = await selectTheme(projectId, themeId);
        setThemes(nextThemes);
        router.refresh();
        setNotice({ title: "主题已选定", message: "当前叙事方向已保存，可继续规划节奏。" });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "选择主题失败，请稍后重试。"
        );
      }
    });
  }

  function handleGenerateWithLlm() {
    setError("");
    const progressState = createLlmProgressState("LLM 主题建议", THEME_LLM_STAGES);
    setLlmProgress(progressState);
    startTransition(async () => {
      try {
        const { data: nextThemes, meta } = await generateThemesWithLlm(
          projectId,
          3,
          (event) => {
            setLlmProgress((current) =>
              current ? applyLlmProgressEvent(current, event) : current
            );
          }
        );
        setThemes(nextThemes);
        router.refresh();
        const llmNotice = describeLlmStatus(meta);
        if (llmNotice) {
          setNotice({
            title: llmNotice.title,
            message: llmNotice.message,
            tone: llmNoticeTone(llmNotice.tone)
          });
        } else {
          setNotice({ title: "LLM 主题建议已更新", message: "已生成新的候选主题方向。" });
        }
      } catch (submitError) {
        const message =
          submitError instanceof Error ? submitError.message : "LLM 主题建议生成失败，请稍后重试。";
        showError(
          message.includes("404") || message.includes("Project not found")
            ? "项目不存在或后端未同步，请返回首页重新进入项目后再试。"
            : message
        );
      } finally {
        setLlmProgress(null);
      }
    });
  }

  return (
    <div className="space-y-4">
      <BlockingNotice
        description="正在处理主题相关操作，请稍候。"
        title="处理中"
        visible={isPending && !llmProgress}
      />
      <LlmProgressOverlay state={llmProgress ?? createLlmProgressState("", THEME_LLM_STAGES)} visible={Boolean(llmProgress)} />
      <ToastNotice
        message={notice?.message ?? ""}
        title={notice?.title ?? ""}
        tone={notice?.tone}
        visible={Boolean(notice)}
      />
      <div className="rounded-[28px] border border-pine/10 bg-mist/70 p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-ink">主题选择区</p>
            <p className="mt-1 text-sm leading-6 text-ink/65">
              先选定一个叙事方向，再进入节奏与分镜。已选主题会置顶展示，候选主题在下方列表中切换。
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={isPending || Boolean(llmProgress)}
              className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPending ? "生成中..." : themes.length > 0 ? "重新生成主题" : "生成主题方向"}
            </button>
            <button
              type="button"
              onClick={handleGenerateWithLlm}
              disabled={isPending || Boolean(llmProgress)}
              className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPending ? "处理中..." : "LLM 建议主题"}
            </button>
          </div>
        </div>
      </div>

      <InlineErrorBanner message={error} />

      {themes.length === 0 ? (
        <EmptyState message="还没有主题方向。先点击上方按钮，系统会基于当前项目和素材生成 3 个候选主题。" />
      ) : (
        <div className="space-y-5">
          {selectedTheme ? (
            <section className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="rounded-full bg-pine px-3 py-1 text-xs font-medium text-white">
                  当前已选主题
                </span>
                <p className="text-sm text-ink/60">后续节奏与分镜会优先参考这一方向。</p>
              </div>
              <ThemeCard
                disabled={isPending || Boolean(llmProgress)}
                onSelect={handleSelect}
                theme={selectedTheme}
              />
            </section>
          ) : null}

          {candidateThemes.length > 0 ? (
            <section className="space-y-3">
              <p className="text-sm font-medium text-ink/75">候选主题</p>
              <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {candidateThemes.map((theme) => (
                  <ThemeCard
                    key={theme.id}
                    disabled={isPending || Boolean(llmProgress)}
                    onSelect={handleSelect}
                    theme={theme}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
