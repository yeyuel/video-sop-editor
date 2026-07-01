"use client";

import type { ChangeEvent, FormEvent } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { ConfirmDialog } from "@/components/ui-primitives";
import {
  CapcutDraftConflictError,
  deployCapcutDraft,
  fetchCapcutExportDefaults,
  importExportCsv,
  importExportJson,
  previewExport,
  saveExportPlan,
  suggestExportPlanWithLlm,
  type ExportImportResult
} from "@/lib/browser-api";
import { describeLlmStatus, llmNoticeTone } from "@/lib/llm-status";
import {
  aiInputClassName,
  AiFieldLabel,
  AiSuggestHint,
  clearSuggestedField
} from "@/lib/ai-field-ui";
import { EXPORT_LLM_STAGES } from "@/lib/llm-progress-stages";
import { useLlmProgress } from "@/lib/use-llm-progress";
import type {
  ExportDocument,
  ExportPlan,
  ExportValidation,
  StoryboardValidation
} from "@/types/domain";

type ExportFormat = "markdown" | "json" | "yaml" | "csv" | "capcut" | "edl";
type ImportFormat = "json" | "csv";
type ConflictStrategy = "overwrite" | "skip";

type ExportPlanClientProps = {
  projectId: string;
  initialPlan: ExportPlan;
  initialJianyingDraftRoot?: string;
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

type ExportSuggestField = "title" | "shortTitle" | "tags" | "description" | "coverSuggestion";

function detectSuggestedFields(
  before: ExportPlan,
  beforeTags: string,
  after: ExportPlan
): ExportSuggestField[] {
  const fields: ExportSuggestField[] = [];
  if (after.title.trim() && after.title !== before.title) {
    fields.push("title");
  }
  if (after.shortTitle.trim() && after.shortTitle !== before.shortTitle) {
    fields.push("shortTitle");
  }
  if (after.tags.length > 0 && joinTags(after.tags) !== beforeTags) {
    fields.push("tags");
  }
  if (after.description.trim() && after.description !== before.description) {
    fields.push("description");
  }
  if (after.coverSuggestion.trim() && after.coverSuggestion !== before.coverSuggestion) {
    fields.push("coverSuggestion");
  }
  return fields;
}

export function ExportPlanClient({
  projectId,
  initialPlan,
  initialJianyingDraftRoot = "",
  storyboardValidation,
  exportValidation
}: ExportPlanClientProps) {
  const router = useRouter();
  const [plan, setPlan] = useState(initialPlan);
  const [tagsText, setTagsText] = useState(joinTags(initialPlan.tags));
  const [jianyingDraftRoot, setJianyingDraftRoot] = useState(initialJianyingDraftRoot);
  const [defaultJianyingDraftRoot, setDefaultJianyingDraftRoot] = useState("");
  const [preview, setPreview] = useState<ExportDocument | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const [isPending, startTransition] = useTransition();
  const { llmProgress, isLlmRunning, start, onProgress, finish } = useLlmProgress();
  const [importFormat, setImportFormat] = useState<ImportFormat>("json");
  const [importContent, setImportContent] = useState("");
  const [importFileName, setImportFileName] = useState("");
  const [conflictStrategy, setConflictStrategy] = useState<ConflictStrategy>("overwrite");
  const [importFields, setImportFields] = useState({ subtitle: true, function: false });
  const [importPreview, setImportPreview] = useState<ExportImportResult | null>(null);
  const [llmSuggestedFields, setLlmSuggestedFields] = useState<ExportSuggestField[]>([]);
  const [deployConfirm, setDeployConfirm] = useState<{ draftFolderPath: string; message: string } | null>(
    null
  );

  useEffect(() => {
    let cancelled = false;
    fetchCapcutExportDefaults(projectId)
      .then((defaults) => {
        if (cancelled) {
          return;
        }
        setDefaultJianyingDraftRoot(defaults.defaultDraftRoot);
        if (!initialJianyingDraftRoot.trim()) {
          setJianyingDraftRoot(defaults.effectiveDraftRoot);
        }
      })
      .catch(() => {
        if (!cancelled && !initialJianyingDraftRoot.trim()) {
          setJianyingDraftRoot("");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, initialJianyingDraftRoot]);

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
        setLlmSuggestedFields([]);
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

  async function runDeployCapcut(clearExisting: boolean) {
    const result = await deployCapcutDraft(projectId, {
      jianyingDraftRoot: jianyingDraftRoot.trim(),
      persistConfig: true,
      clearExisting
    });
    setDeployConfirm(null);
    setNotice({
      title: "剪映草稿已写入",
      message: result.message,
      tone: "success"
    });
  }

  function handleDeployCapcut() {
    setError("");
    startTransition(async () => {
      try {
        await runDeployCapcut(false);
      } catch (submitError) {
        if (submitError instanceof CapcutDraftConflictError) {
          setDeployConfirm({
            draftFolderPath: submitError.draftFolderPath,
            message: submitError.message
          });
          return;
        }
        showError(
          submitError instanceof Error ? submitError.message : "写入剪映草稿目录失败，请稍后重试。"
        );
      }
    });
  }

  function handleConfirmDeployOverwrite() {
    setError("");
    startTransition(async () => {
      try {
        await runDeployCapcut(true);
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "写入剪映草稿目录失败，请稍后重试。"
        );
      }
    });
  }

  function handleSuggestWithLlm() {
    setError("");
    start("导出文案建议", EXPORT_LLM_STAGES);
    startTransition(async () => {
      const beforePlan = plan;
      const beforeTags = tagsText;
      try {
        const { data: nextPlan, meta } = await suggestExportPlanWithLlm(projectId, onProgress);
        setPlan(nextPlan);
        setTagsText(joinTags(nextPlan.tags));
        setLlmSuggestedFields(detectSuggestedFields(beforePlan, beforeTags, nextPlan));
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
      csv: "text/csv;charset=utf-8",
      capcut: "application/json;charset=utf-8",
      edl: "text/plain;charset=utf-8"
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

  function selectedImportFields() {
    const fields: string[] = [];
    if (importFields.subtitle) {
      fields.push("subtitle");
    }
    if (importFields.function) {
      fields.push("function");
    }
    return fields.length > 0 ? fields : ["subtitle"];
  }

  function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const lowerName = file.name.toLowerCase();
    const nextFormat: ImportFormat = lowerName.endsWith(".csv") ? "csv" : "json";
    setImportFormat(nextFormat);
    setImportFileName(file.name);
    setImportPreview(null);

    const reader = new FileReader();
    reader.onload = () => {
      setImportContent(typeof reader.result === "string" ? reader.result : "");
    };
    reader.readAsText(file, "utf-8");
    event.target.value = "";
  }

  function runImport(dryRun: boolean) {
    if (!importContent.trim()) {
      showError("请先上传或粘贴导出 JSON / CSV 内容。");
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        const payload = {
          content: importContent,
          dryRun,
          conflictStrategy,
          fields: selectedImportFields()
        };
        const result =
          importFormat === "csv"
            ? await importExportCsv(projectId, payload)
            : await importExportJson(projectId, payload);
        setImportPreview(result);
        if (result.applied) {
          router.refresh();
          setNotice({
            title: "导入已应用",
            message: `已写回 ${result.updateCount} 处字段变更。`
          });
        } else {
          setNotice({
            title: dryRun ? "导入预览完成" : "无需写入",
            message: `将更新 ${result.updateCount} 处，跳过 ${result.skippedCount} 处，未变化 ${result.unchangedCount} 处。`
          });
        }
      } catch (submitError) {
        showError(submitError instanceof Error ? submitError.message : "导入处理失败，请稍后重试。");
      }
    });
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
      <ConfirmDialog
        open={Boolean(deployConfirm)}
        title="草稿文件夹已存在"
        description={
          deployConfirm
            ? `${deployConfirm.message} 点击「清除并写入」将删除该文件夹内的全部现有文件，然后重新生成草稿。`
            : ""
        }
        subtitle={deployConfirm?.draftFolderPath}
        confirmLabel="清除并写入"
        confirmTone="danger"
        isPending={isPending}
        error={deployConfirm ? error : ""}
        onCancel={() => {
          setDeployConfirm(null);
          setError("");
        }}
        onConfirm={handleConfirmDeployOverwrite}
      />

      <div className="surface-panel p-5">
        <h3 className="text-lg font-semibold text-ink">导出前校验</h3>
        <p className="mt-1 text-sm text-ink/65">
          汇总分镜时长、素材绑定、地点顺序与导出文案一致性，便于发布前快速排查。
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {validationItems.map((item) => (
            <div
              key={item.label}
              className="stat-cell"
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
        {llmSuggestedFields.length > 0 ? (
          <AiSuggestHint className="md:col-span-2" count={llmSuggestedFields.length} />
        ) : null}
        <label className="block md:col-span-2">
          <AiFieldLabel suggested={llmSuggestedFields.includes("title")}>标题</AiFieldLabel>
          <input
            required
            value={plan.title}
            onChange={(event) => {
              setPlan({ ...plan, title: event.target.value });
              setLlmSuggestedFields((current) => clearSuggestedField(current, "title"));
            }}
            placeholder="例如：原来冬天的阿勒泰，真的像童话"
            className={aiInputClassName(llmSuggestedFields.includes("title"))}
          />
        </label>
        <label className="block">
          <AiFieldLabel suggested={llmSuggestedFields.includes("shortTitle")}>短标题</AiFieldLabel>
          <input
            value={plan.shortTitle}
            onChange={(event) => {
              setPlan({ ...plan, shortTitle: event.target.value });
              setLlmSuggestedFields((current) => clearSuggestedField(current, "shortTitle"));
            }}
            placeholder="例如：阿勒泰雪国童话"
            className={aiInputClassName(llmSuggestedFields.includes("shortTitle"))}
          />
        </label>
        <label className="block">
          <AiFieldLabel suggested={llmSuggestedFields.includes("tags")}>标签</AiFieldLabel>
          <input
            required
            value={tagsText}
            onChange={(event) => {
              setTagsText(event.target.value);
              setLlmSuggestedFields((current) => clearSuggestedField(current, "tags"));
            }}
            placeholder="例如：阿勒泰，旅行剪辑，冬日雪景"
            className={aiInputClassName(llmSuggestedFields.includes("tags"))}
          />
        </label>
        <label className="block md:col-span-2">
          <AiFieldLabel suggested={llmSuggestedFields.includes("description")}>文案</AiFieldLabel>
          <textarea
            required
            rows={5}
            value={plan.description}
            onChange={(event) => {
              setPlan({ ...plan, description: event.target.value });
              setLlmSuggestedFields((current) => clearSuggestedField(current, "description"));
            }}
            placeholder="填写最终导出时带上的描述文案，后续可以替换成 LLM 建议结果。"
            className={aiInputClassName(llmSuggestedFields.includes("description"))}
          />
        </label>
        <label className="block md:col-span-2">
          <AiFieldLabel suggested={llmSuggestedFields.includes("coverSuggestion")}>
            封面建议
          </AiFieldLabel>
          <textarea
            rows={3}
            value={plan.coverSuggestion}
            onChange={(event) => {
              setPlan({ ...plan, coverSuggestion: event.target.value });
              setLlmSuggestedFields((current) => clearSuggestedField(current, "coverSuggestion"));
            }}
            placeholder="例如：优先使用禾木木屋群远景，标题放在右下角"
            className={aiInputClassName(llmSuggestedFields.includes("coverSuggestion"))}
          />
        </label>
        {error ? (
          <p className="text-sm text-red-600 md:col-span-2">{error}</p>
        ) : null}
        <label className="block md:col-span-2">
          <span className="mb-1 block text-sm font-medium text-ink">剪映草稿根目录</span>
          <input
            type="text"
            value={jianyingDraftRoot}
            onChange={(event) => setJianyingDraftRoot(event.target.value)}
            placeholder={
              defaultJianyingDraftRoot ||
              "C:\\Users\\你的用户名\\AppData\\Local\\JianyingPro\\User Data\\Projects\\com.lveditor.draft"
            }
            className="input-field font-mono text-sm"
          />
          <p className="mt-1 text-xs text-ink/55">
            一键写入时会在此目录下自动新建草稿文件夹，并落地 draft_content.json 与 draft_meta_info.json。
            {defaultJianyingDraftRoot ? ` 系统默认：${defaultJianyingDraftRoot}` : ""}
          </p>
        </label>
        <div className="flex flex-wrap gap-3 md:col-span-2">
          <button
            type="button"
            onClick={handleDeployCapcut}
            disabled={isPending || isLlmRunning || !jianyingDraftRoot.trim()}
            className="btn-primary"
          >
            {isPending ? "写入中..." : "写入剪映草稿目录"}
          </button>
          <button type="submit" disabled={isPending || isLlmRunning} className="btn-secondary">
            {isPending ? "保存中..." : "保存导出信息"}
          </button>
          <button
            type="button"
            onClick={handleSuggestWithLlm}
            disabled={isPending || isLlmRunning}
            className="btn-ai"
          >
            {isPending ? "处理中..." : "LLM 建议文案"}
          </button>
          <button
            type="button"
            onClick={() => handlePreview("markdown")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            预览 Markdown
          </button>
          <button
            type="button"
            onClick={() => handlePreview("json")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            预览 JSON
          </button>
          <button
            type="button"
            onClick={() => handlePreview("yaml")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            预览 YAML
          </button>
          <button
            type="button"
            onClick={() => handlePreview("csv")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            预览 CSV
          </button>
          <button
            type="button"
            onClick={() => handlePreview("capcut")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            下载剪映草稿 JSON
          </button>
          <button
            type="button"
            onClick={() => handlePreview("edl")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            下载 EDL 粗剪
          </button>
        </div>
      </form>

      <div className="surface-panel p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-ink">导出预览</h3>
            <p className="mt-1 text-sm text-ink/65">
              推荐使用「写入剪映草稿目录」自动落地两个 JSON；也可下载 bundle 手动导入。若节奏页已上传 BGM，导出会自动包含音频轨。
            </p>
          </div>
          {preview ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="stat-pill">{preview.format.toUpperCase()}</span>
              <span className="stat-pill">{preview.fileName}</span>
              <span className="badge">{preview.content.length.toLocaleString()} 字符</span>
              <button type="button" onClick={handleCopyPreview} className="btn-secondary px-4 py-2 text-xs">
                复制内容
              </button>
              <button type="button" onClick={handleDownload} className="btn-primary px-4 py-2 text-xs">
                下载当前预览
              </button>
            </div>
          ) : null}
        </div>
        <textarea
          readOnly
          value={preview?.content ?? ""}
          placeholder="先保存并生成一个导出预览。"
          className="input-field mt-4 min-h-[320px] font-mono bg-sand/30"
        />
      </div>

      <div className="surface-panel p-5">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-pine/70">Round-trip Import</p>
            <h3 className="mt-2 text-lg font-semibold text-ink">反向导入分镜</h3>
            <p className="mt-1 text-sm text-ink/65">
              上传导出的 JSON 或 CSV，预览 diff 后将字幕 / 功能标签写回分镜。dry-run 不会修改数据库。
            </p>
          </div>
          {importFileName ? (
            <span className="badge">{importFileName}</span>
          ) : null}
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">导入文件</span>
            <input
              type="file"
              accept=".json,.csv,application/json,text/csv"
              onChange={handleImportFileChange}
              className="block w-full text-sm text-ink/70 file:mr-4 file:rounded-full file:border-0 file:bg-pine file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-pine/90"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">格式</span>
            <select
              value={importFormat}
              onChange={(event) => {
                setImportFormat(event.target.value as ImportFormat);
                setImportPreview(null);
              }}
              className="input-field"
            >
              <option value="json">导出 JSON（schemaVersion 1.0）</option>
              <option value="csv">导出 CSV（分镜表）</option>
            </select>
          </label>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          <fieldset className="surface-muted px-4 py-3">
            <legend className="px-1 text-sm text-ink/75">冲突策略</legend>
            <div className="mt-2 space-y-2 text-sm text-ink/70">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="conflictStrategy"
                  checked={conflictStrategy === "overwrite"}
                  onChange={() => setConflictStrategy("overwrite")}
                />
                覆盖：incoming 值直接写回
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  name="conflictStrategy"
                  checked={conflictStrategy === "skip"}
                  onChange={() => setConflictStrategy("skip")}
                />
                跳过：当前字段非空且不同则跳过
              </label>
            </div>
          </fieldset>
          <fieldset className="surface-muted px-4 py-3">
            <legend className="px-1 text-sm text-ink/75">写回字段</legend>
            <div className="mt-2 space-y-2 text-sm text-ink/70">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={importFields.subtitle}
                  onChange={(event) =>
                    setImportFields((current) => ({ ...current, subtitle: event.target.checked }))
                  }
                />
                字幕 subtitle（P0）
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={importFields.function}
                  onChange={(event) =>
                    setImportFields((current) => ({ ...current, function: event.target.checked }))
                  }
                />
                功能标签 function（P1）
              </label>
            </div>
          </fieldset>
        </div>

        <label className="mt-4 block">
          <span className="mb-2 block text-sm text-ink/75">文件内容预览</span>
          <textarea
            value={importContent}
            onChange={(event) => {
              setImportContent(event.target.value);
              setImportPreview(null);
            }}
            placeholder="上传 JSON / CSV，或直接粘贴导出内容。"
            className="input-field min-h-[160px] font-mono text-xs bg-sand/30"
          />
        </label>

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => runImport(true)}
            disabled={isPending || isLlmRunning || !importContent.trim()}
            className="btn-secondary"
          >
            {isPending ? "处理中..." : "预览 diff（dry-run）"}
          </button>
          <button
            type="button"
            onClick={() => runImport(false)}
            disabled={isPending || isLlmRunning || !importContent.trim()}
            className="btn-primary"
          >
            {isPending ? "处理中..." : "应用导入"}
          </button>
        </div>

        {importPreview ? (
          <div className="mt-5 overflow-x-auto rounded-2xl border border-pine/10">
            <div className="border-b border-pine/10 bg-sand/40 px-4 py-3 text-sm text-ink/70">
              {importPreview.applied ? "已应用" : importPreview.dryRun ? "预览结果" : "处理结果"} ·
              更新 {importPreview.updateCount} · 跳过 {importPreview.skippedCount} · 未变化{" "}
              {importPreview.unchangedCount}
            </div>
            {importPreview.errors.length > 0 ? (
              <ul className="space-y-1 px-4 py-3 text-sm text-amber-800">
                {importPreview.errors.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : null}
            {importPreview.changes.length === 0 ? (
              <p className="px-4 py-6 text-sm text-ink/55">没有可展示的字段差异。</p>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-pine/10 text-xs uppercase tracking-wide text-ink/55">
                    <th className="px-4 py-3 font-medium">镜头</th>
                    <th className="px-4 py-3 font-medium">字段</th>
                    <th className="px-4 py-3 font-medium">当前值</th>
                    <th className="px-4 py-3 font-medium">导入值</th>
                    <th className="px-4 py-3 font-medium">动作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-pine/8">
                  {importPreview.changes
                    .filter((item) => item.action !== "unchanged")
                    .map((item) => (
                      <tr key={`${item.segmentId}-${item.field}-${item.incomingValue}`}>
                        <td className="px-4 py-3 font-medium text-ink">{item.segmentId}</td>
                        <td className="px-4 py-3 text-ink/70">{item.field}</td>
                        <td className="max-w-xs truncate px-4 py-3 text-ink/65">{item.currentValue || "—"}</td>
                        <td className="max-w-xs truncate px-4 py-3 text-ink/65">{item.incomingValue}</td>
                        <td className="px-4 py-3">
                          <span
                            className={[
                              "inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium",
                              item.action === "update"
                                ? "bg-mist text-pine"
                                : item.action === "skip"
                                  ? "bg-amber-50 text-amber-900"
                                  : "bg-sand text-ink/60"
                            ].join(" ")}
                          >
                            {item.action === "update"
                              ? "将更新"
                              : item.action === "skip"
                                ? "跳过"
                                : "未变化"}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
