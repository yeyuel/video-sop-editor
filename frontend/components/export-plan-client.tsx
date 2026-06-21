"use client";

import type { FormEvent } from "react";
import { useState, useTransition } from "react";
import { previewExport, saveExportPlan } from "@/lib/browser-api";
import type { ExportDocument, ExportPlan } from "@/types/domain";

type ExportPlanClientProps = {
  projectId: string;
  initialPlan: ExportPlan;
};

function joinTags(tags: string[]) {
  return tags.join("，");
}

function splitTags(value: string) {
  return value
    .split(/[，、,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function ExportPlanClient({ projectId, initialPlan }: ExportPlanClientProps) {
  const [plan, setPlan] = useState(initialPlan);
  const [tagsText, setTagsText] = useState(joinTags(initialPlan.tags));
  const [preview, setPreview] = useState<ExportDocument | null>(null);
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await saveExportPlan(projectId, {
          ...plan,
          tags: splitTags(tagsText)
        });
        setPlan(nextPlan);
        setTagsText(joinTags(nextPlan.tags));
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "保存导出信息失败，请稍后重试。"
        );
      }
    });
  }

  function handlePreview(format: "markdown" | "json" | "yaml") {
    setError("");
    startTransition(async () => {
      try {
        const document = await previewExport(projectId, format);
        setPreview(document);
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "生成导出预览失败，请稍后重试。"
        );
      }
    });
  }

  function handleDownload() {
    if (!preview) {
      return;
    }

    const mimeTypeMap: Record<string, string> = {
      markdown: "text/markdown;charset=utf-8",
      json: "application/json;charset=utf-8",
      yaml: "application/x-yaml;charset=utf-8"
    };

    const blob = new Blob([preview.content], {
      type: mimeTypeMap[preview.format] ?? "text/plain;charset=utf-8"
    });
    const downloadUrl = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = downloadUrl;
    anchor.download = preview.fileName;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(downloadUrl);
  }

  return (
    <div className="space-y-6">
      <form className="grid gap-5 md:grid-cols-2" onSubmit={handleSave}>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">标题</span>
          <input
            required
            value={plan.title}
            onChange={(event) => setPlan({ ...plan, title: event.target.value })}
            placeholder="例如：原来冬天的阿勒泰，真的像童话"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">短标题</span>
          <input
            value={plan.shortTitle}
            onChange={(event) => setPlan({ ...plan, shortTitle: event.target.value })}
            placeholder="例如：阿勒泰雪国童话"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">标签</span>
          <input
            required
            value={tagsText}
            onChange={(event) => setTagsText(event.target.value)}
            placeholder="例如：阿勒泰，旅行剪辑，冬日雪景"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">文案</span>
          <textarea
            required
            rows={5}
            value={plan.description}
            onChange={(event) => setPlan({ ...plan, description: event.target.value })}
            placeholder="填写最终导出时带上的描述文案，后续可以替换成 LLM 建议结果。"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">封面建议</span>
          <textarea
            rows={3}
            value={plan.coverSuggestion}
            onChange={(event) => setPlan({ ...plan, coverSuggestion: event.target.value })}
            placeholder="例如：优先使用禾木木屋群远景，标题放在右下角"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        {error ? (
          <p className="text-sm text-red-600 md:col-span-2">{error}</p>
        ) : null}
        <div className="flex flex-wrap gap-3 md:col-span-2">
          <button
            type="submit"
            disabled={isPending}
            className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "保存中..." : "保存导出信息"}
          </button>
          <button
            type="button"
            onClick={() => handlePreview("markdown")}
            disabled={isPending}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 Markdown
          </button>
          <button
            type="button"
            onClick={() => handlePreview("json")}
            disabled={isPending}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 JSON
          </button>
          <button
            type="button"
            onClick={() => handlePreview("yaml")}
            disabled={isPending}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 YAML
          </button>
        </div>
      </form>

      <div className="rounded-xl2 border border-black/5 bg-white/90 p-5 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-ink">导出预览</h3>
            <p className="mt-1 text-sm text-ink/65">
              当前导出会把标题、标签、文案和分镜时间线一起写入输出内容。
            </p>
          </div>
          {preview ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-mist px-3 py-1 text-xs text-pine">
                {preview.fileName}
              </span>
              <button
                type="button"
                onClick={handleDownload}
                className="inline-flex rounded-full bg-pine px-4 py-2 text-xs font-medium text-white transition hover:bg-pine/90"
              >
                下载当前预览
              </button>
            </div>
          ) : null}
        </div>
        <textarea
          readOnly
          value={preview?.content ?? ""}
          placeholder="先保存并生成一个导出预览。"
          className="mt-4 min-h-[320px] w-full rounded-2xl border border-pine/20 bg-sand/30 px-4 py-3 font-mono text-sm outline-none"
        />
      </div>
    </div>
  );
}
