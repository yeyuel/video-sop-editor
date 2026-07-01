"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";
import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { TimeSecondsInput } from "@/components/time-seconds-input";
import { InlineErrorBanner } from "@/components/ui-primitives";
import {
  analyzeAssetVisionStream,
  createAsset,
  getAssetVisionCapability,
  updateAsset,
  type AssetPayload
} from "@/lib/browser-api";
import { describeLlmStatus } from "@/lib/llm-status";
import { VISION_LLM_STAGES } from "@/lib/llm-progress-stages";
import { aiInputClassName, AiFieldLabel, AiSuggestHint, clearSuggestedField } from "@/lib/ai-field-ui";
import { parseTimeSeconds, validateTimeSeconds } from "@/lib/time-input";
import { useLlmProgress } from "@/lib/use-llm-progress";
import type { Asset, LlmVisionCapability } from "@/types/domain";

type AssetFormDefaults = {
  relativePath?: string;
  location?: string;
  mediaType?: string;
};

type AssetFormPrototypeProps = {
  mode: "create" | "edit";
  projectId: string;
  asset?: Asset;
  defaults?: AssetFormDefaults;
  /** 目录树连续录入：保存后不跳转编辑页，保存后回调并跳下一条。 */
  intakeMode?: boolean;
  onIntakeSaved?: (info: { relativePath: string; assetId: string }) => void;
  /** 相对路径 / 媒体类型变更时同步预览区。 */
  onPreviewContextChange?: (context: { relativePath: string; mediaType: string }) => void;
};

type FunctionTagOption = {
  value: string;
  label: string;
  description: string;
};

const mediaTypeOptions = [
  { value: "video", label: "视频" },
  { value: "photo", label: "照片" },
  { value: "audio", label: "音频" },
  { value: "drone_video", label: "航拍视频" },
  { value: "mobile_video", label: "手机视频" },
  { value: "camera_video", label: "相机视频" }
];

const shotTypeOptions = [
  { value: "wide", label: "大景" },
  { value: "medium", label: "中景" },
  { value: "subject_medium", label: "中景含人物/主体" },
  { value: "close_up", label: "特写" },
  { value: "human", label: "人物" },
  { value: "animal", label: "动物" },
  { value: "transition", label: "转场" }
];

const densityOptions = [
  { value: "low", label: "低" },
  { value: "medium", label: "中" },
  { value: "high", label: "高" }
];

const functionTagOptions: FunctionTagOption[] = [
  {
    value: "opening_hook",
    label: "开头钩子",
    description: "用于前 1-3 秒抓注意力。"
  },
  {
    value: "rhythm_hit",
    label: "节奏刺点",
    description: "适合卡强拍、快速切换或情绪提拉。"
  },
  {
    value: "main_climax",
    label: "主高潮",
    description: "用于段落最高点或最有记忆点的镜头。"
  },
  {
    value: "slow_climax",
    label: "慢高潮",
    description: "适合情绪抬升但不靠快切的镜头。"
  },
  {
    value: "transition_buffer",
    label: "过渡缓冲",
    description: "用于地点切换、情绪换挡或承上启下。"
  },
  {
    value: "ending",
    label: "结尾收束",
    description: "用于收尾停顿、回味和落字幕。"
  }
];

function joinTags(value: string[]) {
  return value.join("，");
}

function splitTags(value: string): string[] {
  return value
    .split(/[，,、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function getInitialFunctionTagState(tags: string[]) {
  const knownValues = new Set(functionTagOptions.map((option) => option.value));
  const selected = tags.filter((tag) => knownValues.has(tag));
  const custom = tags.filter((tag) => !knownValues.has(tag));
  return {
    selected,
    customText: joinTags(custom)
  };
}

export function AssetFormPrototype({
  mode,
  projectId,
  asset,
  defaults,
  intakeMode = false,
  onIntakeSaved,
  onPreviewContextChange
}: AssetFormPrototypeProps) {
  const router = useRouter();
  const backHref = `/projects/${projectId}/assets`;
  const [savedAssetId, setSavedAssetId] = useState<string | null>(asset?.assetId ?? null);
  const [isPending, startTransition] = useTransition();
  const { llmProgress, isLlmRunning, start, onProgress, finish } = useLlmProgress();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState<{
    message: string;
    title: string;
    tone?: "error" | "success" | "warning";
  } | null>(null);
  const initialFunctionTags = getInitialFunctionTagState(asset?.functionTags ?? []);
  const [selectedFunctionTags, setSelectedFunctionTags] = useState<string[]>(
    initialFunctionTags.selected
  );
  const [customFunctionTags, setCustomFunctionTags] = useState(
    initialFunctionTags.customText
  );
  const [form, setForm] = useState({
    location: asset?.location ?? defaults?.location ?? "",
    scene: asset?.scene ?? "",
    relativePath: asset?.relativePath ?? defaults?.relativePath ?? "",
    mediaType: asset?.mediaType ?? defaults?.mediaType ?? "video",
    shotType: asset?.shotType ?? "medium",
    emotionTags: joinTags(asset?.emotionTags ?? []),
    visualTags: joinTags(asset?.visualTags ?? []),
    informationDensity: asset?.informationDensity ?? "medium",
    suggestedDurationSec: asset?.suggestedDurationSec?.toString() ?? "1.5"
  });

  useEffect(() => {
    if (asset?.assetId) {
      setSavedAssetId(asset.assetId);
    }
  }, [asset?.assetId]);

  useEffect(() => {
    if (mode !== "create" || !defaults) {
      return;
    }
    setForm((current) => ({
      ...current,
      location: defaults.location ?? current.location,
      relativePath: defaults.relativePath ?? current.relativePath,
      mediaType: defaults.mediaType ?? current.mediaType
    }));
  }, [defaults?.location, defaults?.mediaType, defaults?.relativePath, mode]);

  useEffect(() => {
    onPreviewContextChange?.({
      relativePath: form.relativePath,
      mediaType: form.mediaType
    });
  }, [form.mediaType, form.relativePath, onPreviewContextChange]);

  const [prefilledFields, setPrefilledFields] = useState<string[]>(asset?.visionPrefilledFields ?? []);
  const [visionCapability, setVisionCapability] = useState<LlmVisionCapability | null>(null);

  const activeAssetId = savedAssetId;
  const canVisionAnalyze = Boolean(activeAssetId);
  const canRunVideoVision = form.mediaType !== "audio" && form.mediaType !== "photo";
  const hasVisionPrefill = prefilledFields.length > 0;

  const selectedFunctionDescriptions = useMemo(() => {
    return functionTagOptions
      .filter((option) => selectedFunctionTags.includes(option.value))
      .map((option) => option.label)
      .join(" / ");
  }, [selectedFunctionTags]);

  useEffect(() => {
    let cancelled = false;

    async function loadVisionCapability() {
      try {
        const capability = await getAssetVisionCapability(projectId);
        if (!cancelled) {
          setVisionCapability(capability);
        }
      } catch {
        if (!cancelled) {
          setVisionCapability(null);
        }
      }
    }

    void loadVisionCapability();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  useEffect(() => {
    function handleKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape" && !isPending) {
        router.push(backHref);
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [backHref, isPending, router]);

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

  function showSuccess(title: string, message: string) {
    setError("");
    setNotice({ title, message, tone: "success" });
  }

  function buildPayload(): AssetPayload {
    const durationError = validateTimeSeconds(form.suggestedDurationSec, {
      min: 0,
      required: true
    });
    if (durationError) {
      throw new Error(durationError);
    }

    const suggestedDurationSec = parseTimeSeconds(form.suggestedDurationSec, { min: 0 });
    if (suggestedDurationSec === null || suggestedDurationSec <= 0) {
      throw new Error("建议时长需要大于 0 秒。");
    }

    return {
      location: form.location,
      scene: form.scene,
      relativePath: form.relativePath,
      mediaType: form.mediaType,
      shotType: form.shotType,
      emotionTags: splitTags(form.emotionTags),
      visualTags: splitTags(form.visualTags),
      informationDensity: form.informationDensity,
      suggestedDurationSec,
      functionTags: [...selectedFunctionTags, ...splitTags(customFunctionTags)]
    };
  }

  async function persistAsset(options?: { deferNavigation?: boolean }): Promise<string> {
    const payload = buildPayload();

    if (activeAssetId) {
      await updateAsset(projectId, activeAssetId, payload);
      return activeAssetId;
    }

    const created = await createAsset(projectId, payload);
    setSavedAssetId(created.assetId);
    if (!options?.deferNavigation && !intakeMode) {
      router.replace(`/projects/${projectId}/assets/${created.assetId}/edit`);
    }
    return created.assetId;
  }

  function notifyIntakeSaved(assetId: string) {
    if (!intakeMode || !onIntakeSaved || !form.relativePath.trim()) {
      return;
    }
    onIntakeSaved({ relativePath: form.relativePath.trim(), assetId });
  }

  function applyVisionPrefill(data: {
    scene: string;
    shotType: string;
    emotionTags?: string[];
    visualTags?: string[];
    informationDensity: string;
    suggestedDurationSec: number;
    prefilledFields?: string[];
    message?: string;
  }) {
    const applied: string[] = [];

    setForm((current) => {
      const next = { ...current };

      if (data.scene?.trim()) {
        next.scene = data.scene.trim();
        applied.push("scene");
      }
      if (data.shotType?.trim()) {
        next.shotType = data.shotType.trim();
        applied.push("shotType");
      }
      if ((data.emotionTags ?? []).length) {
        next.emotionTags = joinTags(data.emotionTags ?? []);
        applied.push("emotionTags");
      }
      if ((data.visualTags ?? []).length) {
        next.visualTags = joinTags(data.visualTags ?? []);
        applied.push("visualTags");
      }
      if (data.informationDensity?.trim()) {
        next.informationDensity = data.informationDensity.trim();
        applied.push("informationDensity");
      }
      if (data.suggestedDurationSec > 0) {
        next.suggestedDurationSec = String(data.suggestedDurationSec);
        applied.push("suggestedDurationSec");
      }

      return next;
    });

    setPrefilledFields(applied.length ? applied : data.prefilledFields ?? []);
  }

  async function runVisionAnalyze(assetId: string) {
    if (!form.relativePath.trim()) {
      throw new Error("请先填写素材相对路径。");
    }
    if (visionCapability && !visionCapability.supportsVision) {
      throw new Error(
        visionCapability.message ||
          "当前 LLM 模型不支持图像分析，请联系导演切换 Vision 模型。"
      );
    }

    setError("");
    start("AI 视频分析", VISION_LLM_STAGES);

    try {
      const { data, meta } = await analyzeAssetVisionStream(
        projectId,
        assetId,
        (event) => {
          if (event.type === "progress") {
            onProgress(event);
            return;
          }
          if (event.type === "error") {
            throw new Error(event.message);
          }
        }
      );

      if (data.visionAnalysisStatus === "failed") {
        throw new Error(data.message || "Vision 分析失败。");
      }

      const llmNotice = describeLlmStatus(meta);
      if (llmNotice && llmNotice.tone === "error") {
        throw new Error(llmNotice.message);
      }

      applyVisionPrefill(data);
      showSuccess(
        "AI 分析完成",
        data.message ||
          `已预填 ${(data.prefilledFields ?? []).length} 个字段，确认无误后保存。`
      );
    } finally {
      finish();
    }
  }

  function toggleFunctionTag(value: string) {
    setSelectedFunctionTags((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    );
  }

  function handleVisionAnalyze() {
    if (!canVisionAnalyze || !activeAssetId) {
      showError("请先保存素材（填写地点与相对路径），保存后可直接在本页 AI 分析。");
      return;
    }

    startTransition(async () => {
      try {
        await runVisionAnalyze(activeAssetId);
      } catch (analyzeError) {
        showError(
          analyzeError instanceof Error ? analyzeError.message : "Vision 分析失败，请稍后重试。"
        );
      }
    });
  }

  function handleSaveAndAnalyze() {
    setError("");

    startTransition(async () => {
      try {
        const isNewAsset = !activeAssetId;
        const assetId = await persistAsset({ deferNavigation: true });
        showSuccess(
          isNewAsset ? "素材已创建" : "已保存",
          "正在启动 AI 视频分析…"
        );
        await runVisionAnalyze(assetId);
        router.refresh();
      } catch (actionError) {
        showError(
          actionError instanceof Error ? actionError.message : "保存或分析失败，请稍后重试。"
        );
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    startTransition(async () => {
      try {
        const assetId = await persistAsset({ deferNavigation: intakeMode || mode === "create" });
        setPrefilledFields([]);
        if (intakeMode) {
          notifyIntakeSaved(assetId);
          showSuccess(
            hasVisionPrefill ? "预填内容已保存" : "素材已录入",
            hasVisionPrefill
              ? "已跳下一条未录入文件，可继续录入。"
              : "已选中下一条未录入文件，可继续录入。"
          );
        } else {
          showSuccess(
            hasVisionPrefill ? "预填内容已保存" : mode === "create" ? "素材已创建" : "已保存",
            hasVisionPrefill
              ? "AI 预填字段已写入，可继续编辑或返回列表。"
              : "已留在当前页面，可直接点击「AI 分析」预填字段。"
          );
        }
        router.refresh();
      } catch (submitError) {
        showError(
          submitError instanceof Error ? submitError.message : "保存素材失败，请稍后重试。"
        );
      }
    });
  }

  const visionBlocked = Boolean(visionCapability && !visionCapability.supportsVision);
  const saveLabel = hasVisionPrefill
    ? intakeMode
      ? "确认保存并继续"
      : "确认保存"
    : mode === "create"
      ? intakeMode
        ? "保存并继续下一条"
        : "保存素材"
      : "保存修改";

  return (
    <>
      <BlockingNotice
        visible={isPending && !isLlmRunning}
        title={mode === "create" ? "正在新增素材" : "正在保存素材"}
        description={isPending ? "正在保存素材，请稍候。" : ""}
      />
      <LlmProgressOverlay
        state={
          llmProgress ?? {
            title: "",
            stages: VISION_LLM_STAGES,
            currentStage: "preparing",
            message: "",
            detail: "",
            progress: 0,
            startedAt: Date.now()
          }
        }
        visible={isLlmRunning}
      />
      <ToastNotice
        visible={Boolean(notice)}
        title={notice?.title ?? ""}
        message={notice?.message ?? ""}
        tone={notice?.tone ?? (notice?.title === "操作失败" ? "error" : "success")}
      />
    <div className="surface-panel p-6 md:p-7">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-ink">
          {mode === "create" ? "新增素材" : "编辑素材"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink/70">
          {intakeMode
            ? "从左侧目录选文件后填写或 AI 分析；保存后会自动标记「已录入」并跳下一条，无需重新扫描。"
            : "填写相对路径后可「保存并 AI 分析」一键预填；保存后停留本页，无需返回列表再进入编辑。"}
        </p>
      </div>

      <div className="mb-6 surface-ai p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-ink">AI 视频分析</p>
              <span className="badge-ai">Vision</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-ink/60">
              从视频抽帧并调用 Vision 模型，预填画面内容、镜头类型与标签。
            </p>
            {!canRunVideoVision ? (
              <p className="mt-2 text-xs text-ink/55">当前媒体类型为图片/音频，AI 视频分析不可用。</p>
            ) : null}
            {visionCapability ? (
              <p className="mt-2 text-xs text-ink/55">
                当前模型：{visionCapability.model}
                {visionCapability.supportsVision ? "（支持 Vision）" : "（不支持 Vision）"}
              </p>
            ) : null}
            {!canVisionAnalyze ? (
              <p className="mt-2 text-xs text-ink/55">
                {intakeMode
                  ? "请先保存一次（或使用「保存并 AI 分析」），保存后可直接在本页分析。"
                  : "新建素材请先保存一次；保存后会自动留在编辑页，即可 AI 分析。"}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            disabled={isPending || isLlmRunning || !canVisionAnalyze || visionBlocked || !canRunVideoVision}
            onClick={handleVisionAnalyze}
            className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLlmRunning ? "分析中…" : "AI 分析"}
          </button>
        </div>
        {visionBlocked ? (
          <p className="mt-3 rounded-xl border border-ai/20 bg-white/70 px-3 py-2 text-sm text-ink/75">
            {visionCapability?.message ||
              "当前 LLM 模型不支持图像分析。请联系导演在 LLM 设置中切换到 Vision 模型。"}
          </p>
        ) : null}
        {prefilledFields.length > 0 ? (
          <AiSuggestHint badge="Vision" className="mt-3" count={prefilledFields.length} />
        ) : null}
      </div>

      <form className="grid gap-5 md:grid-cols-2" onSubmit={handleSubmit}>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">地点</span>
          <input
            required
            value={form.location}
            onChange={(event) => setForm({ ...form, location: event.target.value })}
            placeholder="例如：喀纳斯"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">素材相对路径</span>
          <input
            required
            value={form.relativePath}
            onChange={(event) => setForm({ ...form, relativePath: event.target.value })}
            placeholder="例如：喀纳斯/drone/KANAS_001.mp4"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block md:col-span-2">
          <AiFieldLabel badge="Vision" suggested={prefilledFields.includes("scene")}>
            画面内容
          </AiFieldLabel>
          <input
            required
            value={form.scene}
            onChange={(event) => {
              setForm({ ...form, scene: event.target.value });
              setPrefilledFields((current) => clearSuggestedField(current, "scene"));
            }}
            placeholder="例如：蓝冰河流特写，前景带雪面纹理"
            className={aiInputClassName(prefilledFields.includes("scene"))}
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">视频类型</span>
          <select
            value={form.mediaType}
            onChange={(event) => setForm({ ...form, mediaType: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          >
            {mediaTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <AiFieldLabel badge="Vision" suggested={prefilledFields.includes("shotType")}>
            镜头类型
          </AiFieldLabel>
          <select
            value={form.shotType}
            onChange={(event) => {
              setForm({ ...form, shotType: event.target.value });
              setPrefilledFields((current) => clearSuggestedField(current, "shotType"));
            }}
            className={aiInputClassName(prefilledFields.includes("shotType"))}
          >
            {shotTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="mt-2 text-xs text-ink/55">
            “中景含人物/主体”用于表示既有景别信息，又明确带人物或主要主体的镜头类型。
          </p>
        </label>
        <label className="block">
          <AiFieldLabel badge="Vision" suggested={prefilledFields.includes("informationDensity")}>
            信息量
          </AiFieldLabel>
          <select
            value={form.informationDensity}
            onChange={(event) => {
              setForm({ ...form, informationDensity: event.target.value });
              setPrefilledFields((current) => clearSuggestedField(current, "informationDensity"));
            }}
            className={aiInputClassName(prefilledFields.includes("informationDensity"))}
          >
            {densityOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <TimeSecondsInput
          className="md:col-span-1"
          aiSuggested={prefilledFields.includes("suggestedDurationSec")}
          aiBadge="Vision"
          label="建议时长（秒）"
          value={form.suggestedDurationSec}
          required
          onValueChange={(nextValue) => {
            setForm({ ...form, suggestedDurationSec: nextValue });
            setPrefilledFields((current) =>
              clearSuggestedField(current, "suggestedDurationSec")
            );
          }}
        />
        <label className="block">
          <AiFieldLabel badge="Vision" suggested={prefilledFields.includes("emotionTags")}>
            情绪标签
          </AiFieldLabel>
          <input
            value={form.emotionTags}
            onChange={(event) => {
              setForm({ ...form, emotionTags: event.target.value });
              setPrefilledFields((current) => clearSuggestedField(current, "emotionTags"));
            }}
            placeholder="例如：冷，静，童话"
            className={aiInputClassName(prefilledFields.includes("emotionTags"))}
          />
        </label>
        <label className="block">
          <AiFieldLabel badge="Vision" suggested={prefilledFields.includes("visualTags")}>
            视觉标签
          </AiFieldLabel>
          <input
            value={form.visualTags}
            onChange={(event) => {
              setForm({ ...form, visualTags: event.target.value });
              setPrefilledFields((current) => clearSuggestedField(current, "visualTags"));
            }}
            placeholder="例如：冷蓝，白雪，木屋"
            className={aiInputClassName(prefilledFields.includes("visualTags"))}
          />
        </label>
        <div className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">功能标签</span>
          <div className="rounded-2xl border border-pine/30 bg-sand/45 p-3">
            <div className="flex flex-wrap gap-2">
              {functionTagOptions.map((option) => {
                const active = selectedFunctionTags.includes(option.value);

                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => toggleFunctionTag(option.value)}
                    className={[
                      "rounded-full border px-4 py-2 text-sm transition",
                      active
                        ? "border-pine bg-pine text-white"
                        : "border-pine/15 bg-white text-pine hover:bg-mist"
                    ].join(" ")}
                    title={option.description}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <p className="mt-3 text-xs text-ink/55">
              已选推荐标签：{selectedFunctionDescriptions || "暂无"}
            </p>
          </div>
          <input
            value={customFunctionTags}
            onChange={(event) => setCustomFunctionTags(event.target.value)}
            placeholder="可自定义补充，例如：人物出场，地点建立，情绪收束"
            className="mt-3 w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
          <p className="mt-2 text-xs text-ink/55">
            推荐标签用于常见剪辑功能位，自定义内容会和已选标签一起提交。
          </p>
        </div>
        <InlineErrorBanner className="md:col-span-2" message={error} />
        <div className="flex flex-wrap gap-3 md:col-span-2">
          <button
            type="submit"
            disabled={isPending || isLlmRunning}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "保存中..." : saveLabel}
          </button>
          <button
            type="button"
            disabled={isPending || isLlmRunning || visionBlocked || !canRunVideoVision}
            onClick={handleSaveAndAnalyze}
            className="btn-ai disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isLlmRunning ? "分析中..." : isPending ? "处理中..." : "保存并 AI 分析"}
          </button>
          <Link
            href={backHref}
            className="btn-secondary"
          >
            返回素材列表
          </Link>
          <span className="self-center text-xs text-ink/45">Esc 返回列表</span>
        </div>
      </form>
    </div>
    </>
  );
}
