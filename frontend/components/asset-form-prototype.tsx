"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useMemo, useState, useTransition } from "react";
import { createAsset, updateAsset, type AssetPayload } from "@/lib/browser-api";
import type { Asset } from "@/types/domain";

type AssetFormPrototypeProps = {
  mode: "create" | "edit";
  projectId: string;
  asset?: Asset;
};

type FunctionTagOption = {
  value: string;
  label: string;
  description: string;
};

const mediaTypeOptions = [
  { value: "video", label: "视频" },
  { value: "photo", label: "照片" },
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
  asset
}: AssetFormPrototypeProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const initialFunctionTags = getInitialFunctionTagState(asset?.functionTags ?? []);
  const [selectedFunctionTags, setSelectedFunctionTags] = useState<string[]>(
    initialFunctionTags.selected
  );
  const [customFunctionTags, setCustomFunctionTags] = useState(
    initialFunctionTags.customText
  );
  const [form, setForm] = useState({
    location: asset?.location ?? "",
    scene: asset?.scene ?? "",
    relativePath: asset?.relativePath ?? "",
    mediaType: asset?.mediaType ?? "video",
    shotType: asset?.shotType ?? "medium",
    emotionTags: joinTags(asset?.emotionTags ?? []),
    visualTags: joinTags(asset?.visualTags ?? []),
    informationDensity: asset?.informationDensity ?? "medium",
    suggestedDurationSec: asset?.suggestedDurationSec ?? 1.5
  });

  const selectedFunctionDescriptions = useMemo(() => {
    return functionTagOptions
      .filter((option) => selectedFunctionTags.includes(option.value))
      .map((option) => option.label)
      .join(" / ");
  }, [selectedFunctionTags]);

  function toggleFunctionTag(value: string) {
    setSelectedFunctionTags((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value]
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    startTransition(async () => {
      try {
        const payload: AssetPayload = {
          location: form.location,
          scene: form.scene,
          relativePath: form.relativePath,
          mediaType: form.mediaType,
          shotType: form.shotType,
          emotionTags: splitTags(form.emotionTags),
          visualTags: splitTags(form.visualTags),
          informationDensity: form.informationDensity,
          suggestedDurationSec: Number(form.suggestedDurationSec),
          functionTags: [...selectedFunctionTags, ...splitTags(customFunctionTags)]
        };

        if (mode === "create") {
          await createAsset(projectId, payload);
        } else if (asset) {
          await updateAsset(projectId, asset.assetId, payload);
        }

        router.push(`/projects/${projectId}/assets`);
        router.refresh();
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "保存素材失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <div className="rounded-xl2 border border-black/5 bg-white/90 p-6 shadow-card backdrop-blur">
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-ink">
          {mode === "create" ? "新增素材" : "编辑素材"}
        </h2>
        <p className="mt-2 text-sm leading-6 text-ink/70">
          素材 ID 由系统自动生成。项目级配置里保存素材根目录，这里只填写相对路径和内容信息。
        </p>
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
          <span className="mb-2 block text-sm text-ink/75">画面内容</span>
          <input
            required
            value={form.scene}
            onChange={(event) => setForm({ ...form, scene: event.target.value })}
            placeholder="例如：蓝冰河流特写，前景带雪面纹理"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
          <span className="mb-2 block text-sm text-ink/75">镜头类型</span>
          <select
            value={form.shotType}
            onChange={(event) => setForm({ ...form, shotType: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
          <span className="mb-2 block text-sm text-ink/75">信息量</span>
          <select
            value={form.informationDensity}
            onChange={(event) => setForm({ ...form, informationDensity: event.target.value })}
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          >
            {densityOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">建议时长（秒）</span>
          <input
            required
            min={0.1}
            step={0.1}
            type="number"
            value={form.suggestedDurationSec}
            onChange={(event) =>
              setForm({ ...form, suggestedDurationSec: Number(event.target.value) })
            }
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">情绪标签</span>
          <input
            value={form.emotionTags}
            onChange={(event) => setForm({ ...form, emotionTags: event.target.value })}
            placeholder="例如：冷，静，童话"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm text-ink/75">视觉标签</span>
          <input
            value={form.visualTags}
            onChange={(event) => setForm({ ...form, visualTags: event.target.value })}
            placeholder="例如：冷蓝，白雪，木屋"
            className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
        {error ? <p className="text-sm text-red-600 md:col-span-2">{error}</p> : null}
        <div className="flex flex-wrap gap-3 md:col-span-2">
          <button
            type="submit"
            disabled={isPending}
            className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isPending ? "保存中..." : mode === "create" ? "保存素材" : "更新素材"}
          </button>
          <Link
            href={`/projects/${projectId}/assets`}
            className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist"
          >
            返回素材列表
          </Link>
        </div>
      </form>
    </div>
  );
}
