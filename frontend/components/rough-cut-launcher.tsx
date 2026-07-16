"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { LlmProgressOverlay } from "@/components/llm-progress-overlay";
import { generateRoughCutPlan } from "@/lib/browser-api";
import {
  createLlmProgressState,
  ROUGH_CUT_LLM_STAGES
} from "@/lib/llm-progress-stages";
import { useLlmProgress } from "@/lib/use-llm-progress";
import type { RoughCutGenerationResult } from "@/types/domain";

type RoughCutLauncherProps = {
  projectId: string;
  assetCount: number;
};

type GenerationMode = "fill_missing" | "regenerate_creative";

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

  return (
    <>
      <LlmProgressOverlay
        state={
          llmProgress ?? createLlmProgressState("一键初剪", ROUGH_CUT_LLM_STAGES)
        }
        visible={isLlmRunning}
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
      </section>
    </>
  );
}
