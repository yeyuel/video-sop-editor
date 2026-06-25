"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import {
  previewExport,
  saveExportPlan,
  suggestExportPlanWithLlm
} from "@/lib/browser-api";
import { describeLlmStatus, llmNoticeTone } from "@/lib/llm-status";
import { EXPORT_LLM_STAGES } from "@/lib/llm-progress-stages";
import { useLlmProgress } from "@/lib/use-llm-progress";
import type {
  ExportDocument,
  ExportPlan,
  ExportValidation,
  StoryboardValidation
} from "@/types/domain";

type ExportFormat = "markdown" | "json" | "yaml" | "csv";

type ExportPlanClientProps = {
  projectId: string;
  initialPlan: ExportPlan;
  storyboardValidation: StoryboardValidation;
  exportValidation: ExportValidation;
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

function statusTone(passed: boolean) {
  return passed ? "text-pine" : "text-amber-700";
}

export function ExportPlanClient({
  projectId,
  initialPlan,
  storyboardValidation,
  exportValidation
}: ExportPlanClientProps) {
  const router = useRouter();
  const [plan, setPlan] = useState(initialPlan);
  const [tagsText, setTagsText] = useState(joinTags(initialPlan.tags));
  const [preview, setPreview] = useState<ExportDocument | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success";
  } | null>(null);
  const [isPending, startTransition] = useTransition();
  const { llmProgress, isLlmRunning, start, onProgress, finish } = useLlmProgress();

  const validationItems = useMemo(
    () => [
      {
        label: "分镜绑定",
        passed: storyboardValidation.allSegmentsBoundToAsset,
        detail:
          storyboardValidation.unboundSegmentCount > 0
            ? `${storyboardValidation.unboundSegmentCount} 个未绑定`
            : "全部已绑定"
      },
      {
        label: "地点连续性",
        passed: !storyboardValidation.locationOrderValidationEnabled
          ? true
          : storyboardValidation.locationContinuityPassed,
        detail: storyboardValidation.locationOrderValidationEnabled
          ? storyboardValidation.locationContinuityPassed
            ? "顺序正常"
            : "存在跳切风险"
          : "未启用顺序校验"
      },
      {
        label: "时长偏差",
        passed: storyboardValidation.durationWithinTolerance,
        detail: `${storyboardValidation.totalDurationSec}s / 目标 ${storyboardValidation.targetDurationSec}s（${storyboardValidation.durationDeltaSec >= 0 ? "+" : ""}${storyboardValidation.durationDeltaSec}s）`
      },
      {
        label: "导出主题一致",
        passed: exportValidation.themeConsistencyPassed,
        detail: exportValidation.destinationMentioned ? "已提及目的地" : "未提及目的地"
      }
    ],
    [exportValidation, storyboardValidation]
  );

  const openIssues = useMemo(() => {
    const seen = new Set<string>();
    const merged = [...storyboardValidation.issues, ...exportValidation.issues];
    return merged.filter((issue) => {
      if (seen.has(issue)) {
        return false;
      }
      seen.add(issue);
      return true;
    });
  }, [exportValidation.issues, storyboardValidation.issues]);

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
        router.refresh();
        setNotice({ title: "导出信息已保存", message: "标题、标签和文案已写入项目。" });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "保存导出信息失败，请稍后重试。"
        );
      }
    });
  }

  function handlePreview(format: ExportFormat) {
    setError("");
    startTransition(async () => {
      try {
        const document = await previewExport(projectId, format);
        setPreview(document);
        setNotice({ title: "预览已生成", message: `已生成 ${format.toUpperCase()} 格式预览。` });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成导出预览失败，请稍后重试。"
        );
      }
    });
  }

  function handleSuggestWithLlm() {
    setError("");
    start("导出文案建议", EXPORT_LLM_STAGES);
    startTransition(async () => {
      try {
        const { data: nextPlan, meta } = await suggestExportPlanWithLlm(projectId, onProgress);
        setPlan(nextPlan);
        setTagsText(joinTags(nextPlan.tags));
        router.refresh();
        const llmNotice = describeLlmStatus(meta);
        const captionCount = Number(meta?.storyboardCaptionsUpdated ?? 0);
        const captionHint =
          captionCount > 0 ? ` 已同步更新 ${captionCount} 条分镜字幕。` : "";
        if (llmNotice) {
          setNotice({
            title: llmNotice.title,
            message: `${llmNotice.message}${captionHint}`,
            tone: llmNoticeTone(llmNotice.tone)
          });
        } else {
          setNotice({
            title: "LLM 文案建议已更新",
            message: `已填入建议的标题、标签和描述。${captionHint}`.trim()
          });
        }
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成导出建议失败，请稍后重试。"
        );
      } finally {
        finish();
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
      yaml: "application/x-yaml;charset=utf-8",
      csv: "text/csv;charset=utf-8"
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

  async function handleCopyPreview() {
    if (!preview?.content) {
      return;
    }

    try {
      await navigator.clipboard.writeText(preview.content);
      setNotice({ title: "已复制", message: "预览内容已复制到剪贴板。" });
    } catch {
      showError("复制失败，请手动选择预览内容。");
    }
  }

  return (
    <div className="space-y-6">
      <BlockingNotice
        description="正在处理导出相关操作，请稍候。"
        title="处理中"
        visible={isPending && !isLlmRunning}
      />
      <LlmProgressOverlay
        state={llmProgress ?? { title: "", stages: EXPORT_LLM_STAGES, currentStage: "preparing", message: "", detail: "", progress: 0, startedAt: Date.now() }}
        visible={isLlmRunning}
      />
      <ToastNotice
        message={notice?.message ?? ""}
        title={notice?.title ?? ""}
        tone={notice?.tone}
        visible={Boolean(notice)}
      />

      <div className="rounded-xl2 border border-black/5 bg-white/90 p-5 shadow-card">
        <h3 className="text-lg font-semibold text-ink">导出前校验</h3>
        <p className="mt-1 text-sm text-ink/65">
          汇总分镜时长、素材绑定、地点顺序与导出文案一致性，便于发布前快速排查。
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {validationItems.map((item) => (
            <div
              key={item.label}
              className="rounded-2xl border border-pine/10 bg-sand/40 px-4 py-3"
            >
              <p className="text-xs uppercase tracking-[0.18em] text-ink/45">{item.label}</p>
              <p className={`mt-1 text-sm font-medium ${statusTone(item.passed)}`}>
                {item.passed ? "通过" : "待处理"}
              </p>
              <p className="mt-1 text-xs text-ink/60">{item.detail}</p>
            </div>
          ))}
        </div>
        {openIssues.length > 0 ? (
          <ul className="mt-4 space-y-2 text-sm text-amber-800">
            {openIssues.map((issue, index) => (
              <li key={`${index}-${issue}`} className="rounded-xl bg-amber-50 px-3 py-2">
                {issue}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-pine">{exportValidation.message}</p>
        )}
      </div>

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
            disabled={isPending || isLlmRunning}
            className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "保存中..." : "保存导出信息"}
          </button>
          <button
            type="button"
            onClick={handleSuggestWithLlm}
            disabled={isPending || isLlmRunning}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "处理中..." : "LLM 建议文案"}
          </button>
          <button
            type="button"
            onClick={() => handlePreview("markdown")}
            disabled={isPending || isLlmRunning}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 Markdown
          </button>
          <button
            type="button"
            onClick={() => handlePreview("json")}
            disabled={isPending || isLlmRunning}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 JSON
          </button>
          <button
            type="button"
            onClick={() => handlePreview("yaml")}
            disabled={isPending || isLlmRunning}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 YAML
          </button>
          <button
            type="button"
            onClick={() => handlePreview("csv")}
            disabled={isPending || isLlmRunning}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
          >
            预览 CSV
          </button>
        </div>
      </form>

      <div className="rounded-xl2 border border-black/5 bg-white/90 p-5 shadow-card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-ink">导出预览</h3>
            <p className="mt-1 text-sm text-ink/65">
              当前导出会把标题、标签、文案、校验摘要和分镜时间线一起写入输出内容。
            </p>
          </div>
          {preview ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full bg-mist px-3 py-1 text-xs text-pine">
                {preview.format.toUpperCase()}
              </span>
              <span className="rounded-full bg-mist px-3 py-1 text-xs text-pine">
                {preview.fileName}
              </span>
              <span className="rounded-full bg-mist px-3 py-1 text-xs text-ink/60">
                {preview.content.length.toLocaleString()} 字符
              </span>
              <button
                type="button"
                onClick={handleCopyPreview}
                className="inline-flex rounded-full border border-pine/20 bg-white px-4 py-2 text-xs font-medium text-pine transition hover:bg-mist"
              >
                复制内容
              </button>
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
