"use client";

import { useState, useTransition } from "react";
import { generateThemes, selectTheme } from "@/lib/browser-api";
import type { NarrativeTheme } from "@/types/domain";

type ThemeSelectorClientProps = {
  projectId: string;
  initialThemes: NarrativeTheme[];
};

export function ThemeSelectorClient({
  projectId,
  initialThemes
}: ThemeSelectorClientProps) {
  const [themes, setThemes] = useState(initialThemes);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleGenerate() {
    setError("");
    startTransition(async () => {
      try {
        const nextThemes = await generateThemes(projectId, 3);
        setThemes(nextThemes);
      } catch (submitError) {
        setError(
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
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "选择主题失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isPending}
          className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "生成中..." : themes.length > 0 ? "重新生成主题" : "生成主题方向"}
        </button>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      {themes.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-pine/20 bg-white px-4 py-8 text-center text-sm text-ink/60">
          还没有主题方向。先点击上方按钮，系统会基于当前项目和素材生成 3 个候选主题。
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {themes.map((theme) => (
            <article
              key={theme.id}
              className={[
                "rounded-xl2 border p-5 shadow-card transition",
                theme.isSelected
                  ? "border-pine bg-mist"
                  : "border-black/5 bg-white/90 hover:border-pine/25"
              ].join(" ")}
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-lg font-semibold text-ink">{theme.title}</h3>
                <span className="rounded-full bg-white/85 px-3 py-1 text-xs text-pine">
                  {theme.coreEmotion}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-ink/70">{theme.summary}</p>
              <div className="mt-4 space-y-2 text-sm text-ink/70">
                <p>预期节奏：{theme.rhythmProfile}</p>
                <p>平台理由：{theme.platformReason}</p>
              </div>
              <button
                type="button"
                onClick={() => handleSelect(theme.id)}
                disabled={isPending}
                className={[
                  "mt-5 inline-flex rounded-full px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-60",
                  theme.isSelected
                    ? "border border-pine/20 bg-white text-pine"
                    : "bg-pine text-white hover:bg-pine/90"
                ].join(" ")}
              >
                {theme.isSelected ? "当前已选" : "设为当前主题"}
              </button>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
