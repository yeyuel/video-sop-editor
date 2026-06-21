"use client";

import type { FormEvent } from "react";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { generateRhythmPlan, saveRhythmPlan } from "@/lib/browser-api";
import type { RhythmPlan } from "@/types/domain";

type RhythmPlanClientProps = {
  projectId: string;
  initialPlan: RhythmPlan;
};

const beatModeOptions = [
  { value: "none", label: "不启用节拍" },
  { value: "beat_1", label: "节拍 1" },
  { value: "beat_2", label: "节拍 2" },
  { value: "strong_weak", label: "强弱拍" }
];

function listToText(value: string[]) {
  return value.join("\n");
}

function numberListToText(value: number[]) {
  return value.join(", ");
}

function parseTextList(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseNumberList(value: string) {
  return value
    .split(/[,\s]+/)
    .map((item) => Number(item.trim()))
    .filter((item) => !Number.isNaN(item));
}

export function RhythmPlanClient({
  projectId,
  initialPlan
}: RhythmPlanClientProps) {
  const router = useRouter();
  const [plan, setPlan] = useState(initialPlan);
  const [beatPointsText, setBeatPointsText] = useState(numberListToText(initialPlan.beatPoints));
  const [rhythmNotesText, setRhythmNotesText] = useState(listToText(initialPlan.rhythmNotes));
  const [darkCutsText, setDarkCutsText] = useState(numberListToText(initialPlan.darkCutSuggestions));
  const [photoText, setPhotoText] = useState(listToText(initialPlan.photoMotionSuggestions));
  const [error, setError] = useState("");
  const [isPending, startTransition] = useTransition();

  function syncFromPlan(nextPlan: RhythmPlan) {
    setPlan(nextPlan);
    setBeatPointsText(numberListToText(nextPlan.beatPoints));
    setRhythmNotesText(listToText(nextPlan.rhythmNotes));
    setDarkCutsText(numberListToText(nextPlan.darkCutSuggestions));
    setPhotoText(listToText(nextPlan.photoMotionSuggestions));
  }

  function handleGenerate() {
    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await generateRhythmPlan(projectId);
        syncFromPlan(nextPlan);
        router.refresh();
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "生成节奏规划失败，请稍后重试。"
        );
      }
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    startTransition(async () => {
      try {
        const nextPlan = await saveRhythmPlan(projectId, {
          ...plan,
          beatPoints: parseNumberList(beatPointsText),
          rhythmNotes: parseTextList(rhythmNotesText),
          darkCutSuggestions: parseNumberList(darkCutsText),
          photoMotionSuggestions: parseTextList(photoText)
        });
        syncFromPlan(nextPlan);
        router.refresh();
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "保存节奏规划失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isPending}
          className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "生成中..." : "根据项目生成节奏规划"}
        </button>
        <button
          type="submit"
          disabled={isPending}
          className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "保存中..." : "保存节奏规划"}
        </button>
      </div>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <div className="grid gap-5 md:grid-cols-2">
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">BGM 风格</span>
          <input
            required
            value={plan.bgmStyle}
            onChange={(event) => setPlan({ ...plan, bgmStyle: event.target.value })}
            placeholder="例如：冷感氛围电子 + 轻鼓点"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">参考曲目</span>
          <input
            required
            value={plan.selectedTrackName}
            onChange={(event) => setPlan({ ...plan, selectedTrackName: event.target.value })}
            placeholder="例如：snow-dream-demo"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">节拍模式</span>
          <select
            value={plan.beatMode}
            onChange={(event) => setPlan({ ...plan, beatMode: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          >
            {beatModeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">暗场建议点（秒）</span>
          <input
            value={darkCutsText}
            onChange={(event) => setDarkCutsText(event.target.value)}
            placeholder="例如：15, 30, 45"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">节拍点（秒）</span>
          <textarea
            required
            rows={4}
            value={beatPointsText}
            onChange={(event) => setBeatPointsText(event.target.value)}
            placeholder="例如：0, 0.5, 1, 1.5, 2"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
          <p className="mt-2 text-xs text-ink/55">
            分镜生成会优先参考这里的节拍点做卡点切镜，所以 workflow 顺序已经调整为“节奏 → 分镜”。
          </p>
        </label>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">节奏说明</span>
          <textarea
            rows={5}
            value={rhythmNotesText}
            onChange={(event) => setRhythmNotesText(event.target.value)}
            placeholder="每行一条，例如：前 3 秒保证强开头"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block md:col-span-2">
          <span className="mb-2 block text-sm text-ink/75">照片素材动效建议</span>
          <textarea
            rows={4}
            value={photoText}
            onChange={(event) => setPhotoText(event.target.value)}
            placeholder="每行一条，例如：照片素材优先慢推，不和视频一起快切"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
      </div>
    </form>
  );
}
