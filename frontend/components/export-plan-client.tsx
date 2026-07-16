"use client";

import type { ChangeEvent, FormEvent } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { ConfirmDialog } from "@/components/ui-primitives";
import {
  CapcutDraftConflictError,
  deleteExportVoiceoverAudio,
  deployCapcutDraft,
  fetchCapcutExportDefaults,
  fetchVoiceoverProviders,
  getExportVoiceoverAudioUrl,
  importExportCsv,
  importExportJson,
  prepareExportVoiceover,
  previewVoiceoverDensity,
  previewExport,
  saveExportPlan,
  suggestExportPlanWithLlm,
  type ExportImportResult,
  type VoiceoverDensityPreview,
  type VoiceoverProvider
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

type ExportFormat = "markdown" | "json" | "yaml" | "csv" | "capcut" | "edl" | "voiceover";
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

function normalizeVoiceoverLine(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

function buildVoiceoverScriptFromPlan(plan: ExportPlan, tagsText: string) {
  const title = normalizeVoiceoverLine(plan.title);
  const description = normalizeVoiceoverLine(plan.description);
  const shortTitle = normalizeVoiceoverLine(plan.shortTitle);
  const tags = splitTags(tagsText).slice(0, 3).join("、");
  const lines = [
    title ? `开头：${title}。` : "",
    description ? `正文：${description}` : "",
    shortTitle ? `收束：这条路线可以记成“${shortTitle}”。` : "",
    tags ? `补充提示：适合关注${tags}的观众。` : ""
  ].filter(Boolean);
  return lines.join("\n");
}

const voiceoverProviderOptions = [
  { value: "", label: "暂不配置" },
  { value: "mock_silence", label: "本地占位静音 WAV" },
  { value: "jianying_native_tts", label: "剪映原生朗读" },
  { value: "openai", label: "OpenAI / GPT TTS" },
  { value: "edge", label: "Edge / 本地试听" },
  { value: "custom", label: "自定义 Provider" }
];

const voiceoverStyleOptions = [
  { value: "natural", label: "自然讲述" },
  { value: "documentary", label: "纪录片旁白" },
  { value: "guide", label: "旅行向导" },
  { value: "energetic", label: "短视频高能" },
  { value: "soft", label: "治愈轻声" }
];

const voiceoverEmotionOptions = [
  { value: "calm", label: "克制平静" },
  { value: "warm", label: "温暖亲近" },
  { value: "curious", label: "好奇探索" },
  { value: "excited", label: "兴奋种草" },
  { value: "nostalgic", label: "回忆感" }
];

const fallbackEdgeVoiceOptions = [
  { id: "auto", label: "智能匹配", gender: "auto", description: "根据口播风格和情绪自动选择音色。" },
  { id: "zh-CN-XiaoxiaoNeural", label: "晓晓（女声）", gender: "female", description: "自然温暖，适合旅行叙事和治愈内容。" },
  { id: "zh-CN-XiaoyiNeural", label: "晓伊（女声）", gender: "female", description: "明快活泼，适合种草和轻快短视频。" },
  { id: "zh-CN-YunxiNeural", label: "云希（男声）", gender: "male", description: "年轻清晰，适合攻略和旅行向导。" },
  { id: "zh-CN-YunjianNeural", label: "云健（男声）", gender: "male", description: "沉稳有力，适合纪录片和风光旁白。" },
  { id: "zh-CN-YunyangNeural", label: "云扬（男声）", gender: "male", description: "专业清楚，适合信息密集型讲解。" }
];

const voiceoverDensityOptions = [
  {
    value: "light",
    label: "轻口播",
    help: "只保留关键节点，适合氛围片、快切混剪和情绪向旅行短视频。"
  },
  {
    value: "standard",
    label: "标准口播",
    help: "关键节点加必要过渡，适合抖音、小红书常规旅行内容。"
  },
  {
    value: "info",
    label: "信息口播",
    help: "尽量保留路线和攻略信息，适合 B 站攻略类或解释型视频。"
  }
];

function getVoiceoverStatusLabel(status: string) {
  const labels: Record<string, string> = {
    not_generated: "尚未准备",
    provider_required: "缺少 Provider",
    script_required: "缺少口播稿",
    ready: "可生成音频",
    generated: "已生成音频",
    manual_required: "需在剪映中朗读",
    provider_not_supported: "Provider 未接入",
    failed: "生成失败"
  };
  return labels[status] ?? status;
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
  const [voiceoverProviders, setVoiceoverProviders] = useState<VoiceoverProvider[]>([]);
  const [voiceoverPreview, setVoiceoverPreview] = useState<VoiceoverDensityPreview | null>(null);
  const [isVoiceoverPreviewLoading, setIsVoiceoverPreviewLoading] = useState(false);
  const [deployConfirm, setDeployConfirm] = useState<{ draftFolderPath: string; message: string } | null>(
    null
  );

  useEffect(() => {
    let cancelled = false;
    fetchVoiceoverProviders(projectId)
      .then((providers) => {
        if (!cancelled) {
          setVoiceoverProviders(providers);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setVoiceoverProviders([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

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

  useEffect(() => {
    if (plan.voiceoverProvider !== "jianying_native_tts") {
      setVoiceoverPreview(null);
      setIsVoiceoverPreviewLoading(false);
      return;
    }

    let cancelled = false;
    setIsVoiceoverPreviewLoading(true);
    const timer = window.setTimeout(() => {
      previewVoiceoverDensity(projectId, {
        voiceoverDensity: plan.voiceoverDensity ?? "standard",
        voiceoverScript: plan.voiceoverScript ?? "",
        voiceoverSpeed: plan.voiceoverSpeed ?? 1
      })
        .then((result) => {
          if (!cancelled) {
            setVoiceoverPreview(result);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setVoiceoverPreview(null);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setIsVoiceoverPreviewLoading(false);
          }
        });
    }, 250);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [
    plan.voiceoverDensity,
    plan.voiceoverProvider,
    plan.voiceoverScript,
    plan.voiceoverSpeed,
    projectId
  ]);

  const providerOptionsForSelect = useMemo(
    () =>
      voiceoverProviders.length
        ? [
            { value: "", label: "暂不配置" },
            ...voiceoverProviders.map((provider) => ({
              value: provider.id,
              label: provider.isEnabled ? provider.label : `${provider.label}（预留）`
            }))
          ]
        : voiceoverProviderOptions,
    [voiceoverProviders]
  );
  const selectedVoiceoverProvider = useMemo(
    () => voiceoverProviders.find((provider) => provider.id === (plan.voiceoverProvider ?? "")),
    [plan.voiceoverProvider, voiceoverProviders]
  );
  const availableVoiceoverVoices = useMemo(() => {
    if (plan.voiceoverProvider !== "edge") return [];
    return selectedVoiceoverProvider?.voices?.length
      ? selectedVoiceoverProvider.voices
      : fallbackEdgeVoiceOptions;
  }, [plan.voiceoverProvider, selectedVoiceoverProvider]);
  const selectedVoiceoverVoice = availableVoiceoverVoices.find(
    (voice) => voice.id === (plan.voiceoverVoice ?? "auto")
  );
  const voiceoverAudioUrl = getExportVoiceoverAudioUrl(
    projectId,
    plan.voiceoverGeneratedAt || plan.voiceoverAudioPath
  );
  const generatedVoiceLabel =
    typeof plan.voiceoverProviderMeta?.voiceLabel === "string"
      ? plan.voiceoverProviderMeta.voiceLabel
      : "";
  const voiceoverGenerateButtonLabel =
    plan.voiceoverProvider === "jianying_native_tts"
      ? "准备剪映朗读"
      : plan.voiceoverProvider === "edge"
        ? "生成真实口播"
        : plan.voiceoverProvider === "mock_silence"
          ? "生成占位音频"
          : "生成口播音频";
  const selectedVoiceoverDensity = voiceoverDensityOptions.find(
    (option) => option.value === (plan.voiceoverDensity ?? "standard")
  );

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
    const savedPlan = await saveExportPlan(projectId, {
      ...plan,
      tags: splitTags(tagsText)
    });
    setPlan(savedPlan);
    setTagsText(joinTags(savedPlan.tags));

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

  function handleBuildVoiceoverScript() {
    const script = buildVoiceoverScriptFromPlan(plan, tagsText);
    if (!script) {
      showError("请先填写标题或文案，再生成整段口播稿。");
      return;
    }

    setPlan({ ...plan, voiceoverScript: script });
    setNotice({
      title: "口播稿已生成",
      message: "已根据当前标题、文案和标签生成整段口播稿，可继续手动调整。",
      tone: "success"
    });
  }

  function handlePrepareVoiceover() {
    setError("");
    startTransition(async () => {
      try {
        const savedPlan = await saveExportPlan(projectId, {
          ...plan,
          tags: splitTags(tagsText)
        });
        const nextPlan = await prepareExportVoiceover(projectId, {
          dryRun: true,
          useSegmentFallback: true
        });
        setPlan({ ...savedPlan, ...nextPlan });
        setTagsText(joinTags(nextPlan.tags));
        const message =
          typeof nextPlan.voiceoverProviderMeta?.message === "string"
            ? nextPlan.voiceoverProviderMeta.message
            : "已完成口播生成配置检查。";
        setNotice({
          title: getVoiceoverStatusLabel(nextPlan.voiceoverGenerationStatus),
          message,
          tone: nextPlan.voiceoverGenerationStatus === "ready" ? "success" : "warning"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "口播生成配置检查失败，请稍后重试。"
        );
      }
    });
  }

  function handleGenerateVoiceoverAudio() {
    setError("");
    startTransition(async () => {
      try {
        const savedPlan = await saveExportPlan(projectId, {
          ...plan,
          voiceoverProvider: plan.voiceoverProvider || "mock_silence",
          tags: splitTags(tagsText)
        });
        const nextPlan = await prepareExportVoiceover(projectId, {
          dryRun: false,
          useSegmentFallback: true
        });
        setPlan({ ...savedPlan, ...nextPlan });
        setTagsText(joinTags(nextPlan.tags));
        const message =
          typeof nextPlan.voiceoverProviderMeta?.message === "string"
            ? nextPlan.voiceoverProviderMeta.message
            : "口播音频处理完成。";
        const actualVoice =
          typeof nextPlan.voiceoverProviderMeta?.voiceLabel === "string"
            ? ` 本次实际音色：${nextPlan.voiceoverProviderMeta.voiceLabel}。`
            : "";
        setNotice({
          title: getVoiceoverStatusLabel(nextPlan.voiceoverGenerationStatus),
          message: `${message}${actualVoice}`,
          tone: ["generated", "manual_required"].includes(nextPlan.voiceoverGenerationStatus)
            ? "success"
            : "warning"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "生成口播音频失败，请稍后重试。"
        );
      }
    });
  }

  function handleDeleteVoiceoverAudio() {
    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await deleteExportVoiceoverAudio(projectId);
        setPlan(nextPlan);
        setTagsText(joinTags(nextPlan.tags));
        setNotice({
          title: "口播音频已清除",
          message: "已清除当前项目的口播音频路径和生成状态。",
          tone: "success"
        });
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "清除口播音频失败，请稍后重试。"
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
      yaml: "application/x-yaml;charset=utf-8",
      csv: "text/csv;charset=utf-8",
      capcut: "application/json;charset=utf-8",
      edl: "text/plain;charset=utf-8",
      voiceover: "text/plain;charset=utf-8"
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
        <label className="block md:col-span-2">
          <span className="mb-2 flex flex-wrap items-center justify-between gap-3 text-sm font-medium text-ink">
            <span>整段口播稿（可选）</span>
            <button
              type="button"
              onClick={handleBuildVoiceoverScript}
              disabled={isPending || isLlmRunning}
              className="rounded-full border border-pine/20 bg-white px-3 py-1 text-xs text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
            >
              根据文案生成口播稿
            </button>
          </span>
          <textarea
            rows={5}
            value={plan.voiceoverScript ?? ""}
            onChange={(event) => setPlan({ ...plan, voiceoverScript: event.target.value })}
            placeholder="可手动输入整段旁白，也可以先点击“根据文案生成口播稿”生成草稿。"
            className="input-field"
          />
          <p className="mt-1 text-xs text-ink/55">
            这里适合放整条视频的连贯旁白；逐镜头口播仍在分镜详情里维护。
          </p>
        </label>
        <div className="grid gap-4 rounded-3xl border border-pine/15 bg-mist/40 p-4 md:col-span-2 md:grid-cols-4">
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">口播 Provider</span>
            <select
              value={plan.voiceoverProvider ?? ""}
              onChange={(event) =>
                setPlan({
                  ...plan,
                  voiceoverProvider: event.target.value,
                  voiceoverVoice: "auto"
                })
              }
              className="input-field"
            >
              {providerOptionsForSelect.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {selectedVoiceoverProvider ? (
              <p className="mt-2 text-xs leading-5 text-ink/55">
                {selectedVoiceoverProvider.description}
                {!selectedVoiceoverProvider.isEnabled ? " 当前仅作为后续接入预留。" : ""}
              </p>
            ) : null}
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">口播音色</span>
            <select
              value={plan.voiceoverVoice ?? "auto"}
              onChange={(event) => setPlan({ ...plan, voiceoverVoice: event.target.value })}
              disabled={plan.voiceoverProvider !== "edge"}
              className={`input-field ${
                plan.voiceoverProvider !== "edge"
                  ? "cursor-not-allowed bg-sand/60 text-ink/45"
                  : ""
              }`}
            >
              {plan.voiceoverProvider === "edge" ? (
                availableVoiceoverVoices.map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.label}
                  </option>
                ))
              ) : (
                <option value="auto">
                  {plan.voiceoverProvider === "jianying_native_tts"
                    ? "在剪映中选择"
                    : "当前 Provider 不支持"}
                </option>
              )}
            </select>
            <p className="mt-2 text-xs leading-5 text-ink/55">
              {plan.voiceoverProvider === "edge"
                ? selectedVoiceoverVoice?.description ?? "选择用于生成口播的具体音色。"
                : plan.voiceoverProvider === "jianying_native_tts"
                  ? "剪映音色需在打开草稿后使用专业版音色库选择。"
                  : "选择 Edge TTS 后可指定中文男女声。"}
            </p>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">口播风格</span>
            <select
              value={plan.voiceoverStyle ?? "natural"}
              onChange={(event) => setPlan({ ...plan, voiceoverStyle: event.target.value })}
              className="input-field"
            >
              {voiceoverStyleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">口播情绪</span>
            <select
              value={plan.voiceoverEmotion ?? "calm"}
              onChange={(event) => setPlan({ ...plan, voiceoverEmotion: event.target.value })}
              className="input-field"
            >
              {voiceoverEmotionOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">口播密度</span>
            <select
              value={plan.voiceoverDensity ?? "standard"}
              onChange={(event) => setPlan({ ...plan, voiceoverDensity: event.target.value })}
              className="input-field"
            >
              {voiceoverDensityOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {selectedVoiceoverDensity ? (
              <p className="mt-2 text-xs leading-5 text-ink/55">
                {selectedVoiceoverDensity.help}
              </p>
            ) : null}
          </label>
          <label className="block">
            <span className="mb-2 flex items-center justify-between gap-2 text-sm text-ink/75">
              <span>语速倍率</span>
              <strong className="text-pine">{(plan.voiceoverSpeed ?? 1).toFixed(2)}x</strong>
            </span>
            <div className="rounded-2xl border border-pine/20 bg-white px-4 py-3">
              <input
                type="range"
                min={0.7}
                max={1.3}
                step={0.05}
                value={plan.voiceoverSpeed ?? 1}
                onChange={(event) =>
                  setPlan({ ...plan, voiceoverSpeed: Number(event.target.value) })
                }
                className="h-2 w-full cursor-pointer accent-pine"
              />
              <div className="mt-1 flex justify-between text-[11px] text-ink/45">
                <span>0.70x 慢</span>
                <button
                  type="button"
                  onClick={() => setPlan({ ...plan, voiceoverSpeed: 1 })}
                  className="text-pine hover:underline"
                >
                  恢复 1.00x
                </button>
                <span>1.30x 快</span>
              </div>
            </div>
          </label>
          {["jianying_native_tts", "edge"].includes(plan.voiceoverProvider ?? "") ? (
            <div className="rounded-2xl border border-pine/15 bg-white/65 p-4 md:col-span-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium text-ink">最终字幕与口播评估</p>
                  <p className="mt-1 text-xs text-ink/55">
                    {plan.voiceoverProvider === "edge"
                      ? "压缩后的文本会同时用于真实口播和最终字幕；生成后字幕时间会按实际发音边界对齐。"
                      : "压缩后的文本会同时作为最终字幕和剪映朗读源，实际朗读时长会受剪映音色影响。"}
                  </p>
                </div>
                {isVoiceoverPreviewLoading ? (
                  <span className="text-xs text-pine">正在重新计算...</span>
                ) : voiceoverPreview &&
                  Math.abs(voiceoverPreview.recommendedSpeed - (plan.voiceoverSpeed ?? 1)) >=
                    0.04 ? (
                  <button
                    type="button"
                    onClick={() =>
                      setPlan({ ...plan, voiceoverSpeed: voiceoverPreview.recommendedSpeed })
                    }
                    className="rounded-full border border-pine/20 bg-white px-3 py-1 text-xs text-pine transition hover:bg-mist"
                  >
                    应用建议 {voiceoverPreview.recommendedSpeed.toFixed(2)}x
                  </button>
                ) : null}
              </div>
              {voiceoverPreview ? (
                <>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    <div className="rounded-xl bg-mist/60 px-3 py-2 text-sm text-ink/70">
                      朗读字数：<strong className="text-ink">{voiceoverPreview.outputChars}</strong>
                      <span className="text-ink/45"> / {voiceoverPreview.sourceChars}</span>
                    </div>
                    <div className="rounded-xl bg-mist/60 px-3 py-2 text-sm text-ink/70">
                      压缩比例：
                      <strong className="text-ink">
                        {Math.round(voiceoverPreview.compressionRatio * 100)}%
                      </strong>
                    </div>
                    <div className="rounded-xl bg-mist/60 px-3 py-2 text-sm text-ink/70">
                      口播块：<strong className="text-ink">{voiceoverPreview.blockCount}</strong>
                    </div>
                    <div className="rounded-xl bg-mist/60 px-3 py-2 text-sm text-ink/70">
                      预计朗读：
                      <strong className="text-ink">{voiceoverPreview.estimatedReadingSec}s</strong>
                    </div>
                  </div>
                  <p
                    className={`mt-3 text-xs ${
                      voiceoverPreview.timingRiskCount > 0 ? "text-amber-700" : "text-pine"
                    }`}
                  >
                    {voiceoverPreview.timingRiskCount > 0
                      ? `${voiceoverPreview.timingRiskCount} 个口播块仍存在读不完风险，建议降低密度或提高语速。`
                      : "所有口播块均已预留起音、标点停顿和收尾时间。"}
                  </p>
                  {voiceoverPreview.alignmentRiskCount > 0 ? (
                    <p className="mt-1 text-xs text-amber-700">
                      {voiceoverPreview.alignmentRiskCount} 个口播块为保证读完已提前进入，展开下方片段可查看原画面区间和建议倍速。
                    </p>
                  ) : (
                    <p className="mt-1 text-xs text-pine">口播起止时间与对应画面区间保持一致。</p>
                  )}
                  {voiceoverPreview.blocks.length > 0 ? (
                    <details className="mt-3 rounded-xl bg-mist/35 px-3 py-2">
                      <summary className="cursor-pointer text-xs font-medium text-pine">
                        查看最终字幕与口播片段
                      </summary>
                      <div className="mt-2 space-y-2">
                        {voiceoverPreview.blocks.map((block, index) => (
                          <div
                            key={`${block.startTime}-${index}`}
                            className="rounded-lg border border-pine/10 bg-white/70 px-3 py-2 text-xs leading-5 text-ink/65"
                          >
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                              <span className="font-medium text-pine">
                                字幕/口播 {block.startTime}s - {block.endTime}s
                              </span>
                              <span>
                                画面 {block.sourceStartTime}s - {block.sourceEndTime}s
                              </span>
                              <span>预计 {block.estimatedReadingSec}s</span>
                              {block.alignmentStatus === "speed_recommended" ? (
                                <span className="text-amber-700">
                                  建议 {Math.min(1.3, block.recommendedSpeed).toFixed(2)}x
                                </span>
                              ) : block.alignmentStatus === "needs_trim_or_extend" ? (
                                <span className="text-clay">建议精简文案或延长画面</span>
                              ) : (
                                <span className="text-pine">已对齐</span>
                              )}
                            </div>
                            <p className="mt-1 text-ink/75">{block.text}</p>
                          </div>
                        ))}
                      </div>
                    </details>
                  ) : (
                    <p className="mt-3 text-xs text-amber-700">当前分镜没有可用于朗读的字幕或口播文本。</p>
                  )}
                </>
              ) : !isVoiceoverPreviewLoading ? (
                <p className="mt-3 text-xs text-amber-700">暂时无法计算口播密度，请确认后端服务已启动。</p>
              ) : null}
            </div>
          ) : null}
          <p className="text-xs leading-5 text-ink/55 md:col-span-4">
            当前 `mock_silence` 可生成本地占位音频，`jianying_native_tts`
            会在剪映草稿中写入统一的“最终字幕（剪映朗读源）”文本轨；真实云端 TTS Provider 后续接入时会复用这些参数。
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white/70 px-4 py-3 md:col-span-4">
            <div className="text-sm text-ink/70">
              <span className="font-medium text-ink">
                {getVoiceoverStatusLabel(plan.voiceoverGenerationStatus)}
              </span>
              <span className="ml-3">
                预计时长：{plan.voiceoverDurationSec ? `${plan.voiceoverDurationSec}s` : "未计算"}
              </span>
              {plan.voiceoverGeneratedAt ? (
                <span className="ml-3">检查时间：{plan.voiceoverGeneratedAt}</span>
              ) : null}
            </div>
            <button
              type="button"
              onClick={handlePrepareVoiceover}
              disabled={isPending || isLlmRunning}
              className="btn-secondary px-4 py-2 text-xs"
            >
              检查口播生成配置
            </button>
            <button
              type="button"
              onClick={handleGenerateVoiceoverAudio}
              disabled={isPending || isLlmRunning}
              className="btn-secondary px-4 py-2 text-xs"
            >
              {voiceoverGenerateButtonLabel}
            </button>
            {plan.voiceoverAudioPath ? (
              <button
                type="button"
                onClick={handleDeleteVoiceoverAudio}
                disabled={isPending || isLlmRunning}
                className="rounded-full border border-clay/20 bg-white px-4 py-2 text-xs text-clay transition hover:bg-[#fff5ef] disabled:cursor-not-allowed disabled:opacity-60"
              >
                清除音频
              </button>
            ) : null}
          </div>
          {plan.voiceoverAudioPath ? (
            <div className="rounded-2xl bg-white/70 px-4 py-3 md:col-span-4">
              <p className="mb-2 text-xs text-ink/55">
                {plan.voiceoverProvider === "edge"
                  ? `当前音频由 Edge TTS 生成${
                      generatedVoiceLabel ? `，实际音色：${generatedVoiceLabel}` : ""
                    }，可试听、下载并直接写入剪映草稿。`
                  : "当前音频是本地占位静音 WAV，仅用于验证链路，不代表真实口播效果。"}
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <audio
                  key={voiceoverAudioUrl}
                  controls
                  src={voiceoverAudioUrl}
                  className="h-10 min-w-[280px]"
                />
                <a
                  href={voiceoverAudioUrl}
                  download
                  className="btn-secondary px-4 py-2 text-xs"
                >
                  下载音频
                </a>
              </div>
            </div>
          ) : null}
        </div>
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
            onClick={() => handlePreview("voiceover")}
            disabled={isPending || isLlmRunning}
            className="btn-secondary"
          >
            预览口播稿
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
