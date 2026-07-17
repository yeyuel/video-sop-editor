"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import {
  fetchRoughCutVersions,
  generateRoughCutPlan,
  rerunRoughCutStep,
  restoreRoughCutVersion
} from "@/lib/browser-api";
import {
  createLlmProgressState,
  ROUGH_CUT_LLM_STAGES
} from "@/lib/llm-progress-stages";
import { useLlmProgress } from "@/lib/use-llm-progress";
import type { RoughCutGenerationResult, RoughCutVersion } from "@/types/domain";

type RoughCutLauncherProps = {
  projectId: string;
  assetCount: number;
};

type GenerationMode = "fill_missing" | "regenerate_creative";
type RerunStep = "theme" | "storyboard" | "export";

const modeOptions: Array<{
  value: GenerationMode;
  title: string;
  description: string;
}> = [
  {
    value: "fill_missing",
    title: "补齐缺失阶段",
    description: "保留已确认的主题、分镜与文案，只补齐还没有完成的内容。"
  },
  {
    value: "regenerate_creative",
    title: "从头生成创意方案",
    description: "备份当前方案，重新生成主题、分镜与文案；已上传的音频和校准节拍保持不变。"
  }
];

export function RoughCutLauncher({ projectId, assetCount }: RoughCutLauncherProps) {
  const router = useRouter();
  const { llmProgress, isLlmRunning, start, onProgress, finish } = useLlmProgress();
  const [mode, setMode] = useState<GenerationMode>("fill_missing");
  const [result, setResult] = useState<RoughCutGenerationResult | null>(null);
  const [error, setError] = useState("");
  const [versions, setVersions] = useState<RoughCutVersion[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(true);
  const [restoreTarget, setRestoreTarget] = useState<RoughCutVersion | null>(null);
  const [restoring, setRestoring] = useState(false);
  const [restoreMessage, setRestoreMessage] = useState("");
  const [runningStep, setRunningStep] = useState<RerunStep | null>(null);

  async function loadVersions() {
    try {
      setVersions(await fetchRoughCutVersions(projectId));
    } catch {
      setVersions([]);
    } finally {
      setVersionsLoading(false);
    }
  }

  useEffect(() => {
    void loadVersions();
  }, [projectId]);

  useEffect(() => {
    if (!restoreMessage) return;
    const timer = window.setTimeout(() => setRestoreMessage(""), 3600);
    return () => window.clearTimeout(timer);
  }, [restoreMessage]);

  async function handleGenerate() {
    setError("");
    setResult(null);
    start(
      mode === "regenerate_creative" ? "正在从头生成创意方案" : "正在补齐初剪方案",
      ROUGH_CUT_LLM_STAGES
    );
    try {
      const response = await generateRoughCutPlan(projectId, mode, onProgress);
      setResult(response.data);
      await loadVersions();
      router.refresh();
    } catch (generationError) {
      setError(
        generationError instanceof Error
          ? generationError.message
          : "初剪方案生成失败，请重试。"
      );
    } finally {
      finish();
    }
  }

  const regenerate = mode === "regenerate_creative";

  async function handleRestore() {
    if (!restoreTarget) return;
    setError("");
    setRestoring(true);
    try {
      const response = await restoreRoughCutVersion(projectId, restoreTarget.id);
      setRestoreMessage(response.message);
      setRestoreTarget(null);
      await loadVersions();
      router.refresh();
    } catch (restoreError) {
      setError(
        restoreError instanceof Error ? restoreError.message : "历史方案恢复失败，请重试。"
      );
    } finally {
      setRestoring(false);
    }
  }

  async function handleRerun(step: RerunStep) {
    const labels: Record<RerunStep, string> = {
      theme: "主题",
      storyboard: "分镜",
      export: "导出文案"
    };
    setError("");
    setResult(null);
    setRunningStep(step);
    start(`正在重新生成${labels[step]}`, ROUGH_CUT_LLM_STAGES);
    try {
      const response = await rerunRoughCutStep(projectId, step, onProgress);
      setResult(response.data);
      await loadVersions();
      router.refresh();
    } catch (rerunError) {
      setError(
        rerunError instanceof Error ? rerunError.message : `${labels[step]}重跑失败，请重试。`
      );
    } finally {
      setRunningStep(null);
      finish();
    }
  }

  return (
    <>
      <LlmProgressOverlay
        state={
          llmProgress ?? createLlmProgressState("一键初剪", ROUGH_CUT_LLM_STAGES)
        }
        visible={isLlmRunning}
      />
      <BlockingNotice
        visible={restoring}
        title="正在恢复历史方案"
        description="系统正在备份当前方案并恢复主题、分镜和导出文案。"
      />
      <ToastNotice
        visible={Boolean(restoreMessage)}
        title="恢复完成"
        message={restoreMessage}
      />
      <section className="surface-panel mb-5 overflow-hidden p-6">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="max-w-2xl">
            <p className="eyebrow">QUICK ROUGH CUT</p>
            <h2 className="mt-2 text-2xl font-semibold text-ink">一键准备初剪方案</h2>
            <p className="mt-2 text-sm leading-6 text-ink/65">
              可选择安全补齐缺失内容，或切换 LLM 后从头生成一套创意方案进行对比。
              生成完成后仍需在导出页确认并写入剪映草稿。
            </p>
          </div>
          <button
            type="button"
            className="btn-primary"
            disabled={assetCount === 0 || isLlmRunning}
            onClick={handleGenerate}
          >
            {isLlmRunning
              ? "生成中..."
              : regenerate
                ? "重新生成并保留版本"
                : "补齐初剪方案"}
          </button>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {modeOptions.map((option) => {
            const selected = mode === option.value;
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={selected}
                disabled={isLlmRunning}
                onClick={() => setMode(option.value)}
                className={`rounded-2xl border px-4 py-4 text-left transition ${
                  selected
                    ? "border-pine bg-mist shadow-sm"
                    : "border-pine/15 bg-white/70 hover:border-pine/35"
                }`}
              >
                <span className="flex items-center gap-2 font-medium text-ink">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      selected ? "bg-pine" : "bg-ink/20"
                    }`}
                  />
                  {option.title}
                  {option.value === "fill_missing" ? (
                    <span className="rounded-full bg-sand px-2 py-0.5 text-xs font-normal text-ink/60">
                      推荐
                    </span>
                  ) : null}
                </span>
                <span className="mt-2 block text-sm leading-6 text-ink/60">
                  {option.description}
                </span>
              </button>
            );
          })}
        </div>

        {regenerate ? (
          <p className="mt-3 rounded-2xl bg-sand/60 px-4 py-3 text-sm leading-6 text-ink/65">
            当前主题、分镜和导出文案会先保存为历史快照。新方案使用当前启用的
            LLM；真实音频、节拍识别与人工偏移不会重算。
          </p>
        ) : null}
        {assetCount === 0 ? (
          <p className="mt-4 rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/65">
            请先录入素材，再启动一键初剪。
          </p>
        ) : null}
        {error ? (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay">
            <span>{error}</span>
            <button type="button" className="font-medium underline" onClick={handleGenerate}>
              使用相同配置重试
            </button>
          </div>
        ) : null}
        {result ? (
          <div className="mt-4 rounded-2xl bg-mist px-4 py-3 text-sm text-ink/75">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>{result.message}</span>
              <Link className="font-medium text-pine underline" href={result.nextPath}>
                {result.status === "waiting_audio" ? "去选择并上传音乐" : "检查并导出"}
              </Link>
            </div>
            {result.model ? (
              <p className="mt-2 text-xs text-ink/55">
                本次模型：{result.providerId} / {result.model}
                {result.generatedVersionId ? " · 已保存生成版本" : ""}
                {result.preservedAudioRhythm ? " · 已复用真实节拍" : ""}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-6 border-t border-pine/10 pt-5">
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-sand/45 px-4 py-4">
            <div>
              <h3 className="font-semibold text-ink">单步骤重跑</h3>
              <p className="mt-1 text-sm text-ink/55">
                只覆盖选定阶段，并自动保存重跑前后的方案版本。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {([
                ["theme", "重跑主题"],
                ["storyboard", "重跑分镜"],
                ["export", "重跑导出文案"]
              ] as Array<[RerunStep, string]>).map(([step, label]) => (
                <button
                  key={step}
                  type="button"
                  disabled={isLlmRunning || restoring}
                  onClick={() => handleRerun(step)}
                  className="rounded-full border border-pine/20 bg-white px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {runningStep === step ? "生成中..." : label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-ink">方案版本</h3>
              <p className="mt-1 text-sm text-ink/55">
                对比不同模型或生成批次；恢复只影响主题、分镜和导出文案。
              </p>
            </div>
            {versions.length > 0 ? (
              <span className="rounded-full bg-sand px-3 py-1 text-xs text-ink/60">
                {versions.length} 个版本
              </span>
            ) : null}
          </div>

          {versionsLoading ? (
            <p className="mt-4 text-sm text-ink/50">正在读取历史版本...</p>
          ) : versions.length === 0 ? (
            <p className="mt-4 rounded-2xl bg-sand/45 px-4 py-4 text-sm text-ink/60">
              暂无历史版本。使用“从头生成创意方案”后会自动保存版本快照。
            </p>
          ) : (
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {versions.slice(0, 8).map((version) => {
                const differs =
                  version.diff.themeChanged ||
                  version.diff.storyboardCountDelta !== 0 ||
                  version.diff.durationDeltaSec !== 0 ||
                  version.diff.sequenceChangeCount !== 0 ||
                  version.diff.exportTitleChanged;
                return (
                  <article
                    key={version.id}
                    className="rounded-2xl border border-pine/12 bg-white/75 p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{version.label}</p>
                        <p className="mt-1 text-xs text-ink/45">
                          {new Date(version.createdAt).toLocaleString("zh-CN")}
                          {version.model ? ` · ${version.providerId}/${version.model}` : ""}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 rounded-full px-2.5 py-1 text-xs ${
                          differs ? "bg-sand text-ink/65" : "bg-mist text-pine"
                        }`}
                      >
                        {differs ? "存在差异" : "与当前一致"}
                      </span>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink/60">
                      <span className="rounded-xl bg-sand/45 px-3 py-2">
                        主题：{version.summary.themeTitle || "未设置"}
                      </span>
                      <span className="rounded-xl bg-sand/45 px-3 py-2">
                        {version.summary.storyboardCount} 镜头 · {version.summary.durationSec}s
                      </span>
                      <span className="col-span-2 truncate rounded-xl bg-sand/45 px-3 py-2">
                        标题：{version.summary.exportTitle || "未设置"}
                      </span>
                    </div>
                    {differs ? (
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-ink/55">
                        {version.diff.themeChanged ? <span>主题不同</span> : null}
                        {version.diff.sequenceChangeCount ? (
                          <span>{version.diff.sequenceChangeCount} 个镜头位置不同</span>
                        ) : null}
                        {version.diff.storyboardCountDelta ? (
                          <span>
                            镜头数 {version.diff.storyboardCountDelta > 0 ? "+" : ""}
                            {version.diff.storyboardCountDelta}
                          </span>
                        ) : null}
                        {version.diff.durationDeltaSec ? (
                          <span>
                            时长 {version.diff.durationDeltaSec > 0 ? "+" : ""}
                            {version.diff.durationDeltaSec}s
                          </span>
                        ) : null}
                        {version.diff.exportTitleChanged ? <span>标题不同</span> : null}
                      </div>
                    ) : null}
                    <button
                      type="button"
                      disabled={!differs || restoring}
                      onClick={() => setRestoreTarget(version)}
                      className="mt-4 rounded-full border border-pine/20 px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      恢复此版本
                    </button>
                  </article>
                );
              })}
            </div>
          )}
          </div>
        </div>

        {restoreTarget ? (
          <div className="mt-4 rounded-2xl border border-clay/20 bg-[#fff8f2] p-4">
            <p className="font-medium text-ink">确认恢复“{restoreTarget.label}”？</p>
            <p className="mt-2 text-sm leading-6 text-ink/60">
              当前方案会先自动备份。恢复不会覆盖素材库、真实音频和节拍校准，但旧口播音频会被清除，避免文案与声音不一致。
            </p>
            <div className="mt-4 flex gap-3">
              <button type="button" className="btn-primary" onClick={handleRestore}>
                确认恢复
              </button>
              <button
                type="button"
                className="rounded-full border border-pine/20 px-5 py-2.5 text-sm text-pine"
                onClick={() => setRestoreTarget(null)}
              >
                取消
              </button>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}
