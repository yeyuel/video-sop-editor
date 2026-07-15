"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState, useTransition } from "react";

import { BlockingNotice, ToastNotice } from "@/components/async-status";
import { createProject, updateProject, type ProjectPayload } from "@/lib/browser-api";
import type { Project } from "@/types/domain";

type ProjectBasicsPrototypeProps = {
  mode: "create" | "edit";
  project?: Project;
  submitLabel?: string;
  backHref?: string;
  /** 嵌入 SectionCard 时隐藏外层卡片与重复标题 */
  embedded?: boolean;
};

type ProjectFormState = Omit<
  ProjectPayload,
  "targetDurationSec" | "durationFillMaxConsecutiveRoute"
> & {
  targetDurationSec: string;
  durationFillMaxConsecutiveRoute: string;
};

const styleOptions = [
  {
    value: "情绪氛围片",
    label: "情绪氛围片",
    description: "适合雪景、山野、清晨、空镜较多的素材，重点放在氛围和沉浸感。"
  },
  {
    value: "路线纪实片",
    label: "路线纪实片",
    description: "适合地点切换明确、路线推进感强的旅行记录。"
  },
  {
    value: "人物陪伴感 Vlog",
    label: "人物陪伴感 Vlog",
    description: "适合人物镜头占比更高，需要陪伴感和口播感的内容。"
  },
  {
    value: "旅行攻略片",
    label: "旅行攻略片",
    description: "适合信息点清楚、节奏利落、强调实用价值的短视频。"
  },
  {
    value: "城市漫游片",
    label: "城市漫游片",
    description: "适合街景、建筑、夜景和步行视角混剪。"
  }
];

const videoTypeOptions = [
  { value: "emotion_film", label: "情绪片" },
  { value: "travel_montage", label: "旅行混剪" },
  { value: "guide_video", label: "攻略短片" },
  { value: "city_short", label: "城市短片" },
  { value: "vlog", label: "Vlog" }
];

const platformOptions = [
  { value: "xiaohongshu", label: "小红书" },
  { value: "douyin", label: "抖音" },
  { value: "wechat_channel", label: "视频号" },
  { value: "bilibili", label: "Bilibili" }
];

export function ProjectBasicsPrototype({
  mode,
  project,
  submitLabel = mode === "create" ? "保存并进入素材录入" : "保存项目",
  backHref = "/",
  embedded = false
}: ProjectBasicsPrototypeProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);
  const [form, setForm] = useState<ProjectFormState>({
    name: project?.name ?? "",
    destination: project?.destination ?? "",
    platform: project?.platform ?? "xiaohongshu",
    targetDurationSec: project?.targetDurationSec?.toString() ?? "60",
    videoType: project?.videoType ?? "emotion_film",
    stylePreference: project?.stylePreference ?? styleOptions[0].value,
    styleNotes: project?.styleNotes ?? "",
    routeText: project?.routeText ?? "",
    mediaRoot: project?.mediaRoot ?? "",
    jianyingDraftRoot: project?.jianyingDraftRoot ?? "",
    status: project?.status ?? "draft",
    validateLocationOrder: project?.validateLocationOrder ?? false,
    allowAssetReuse: project?.allowAssetReuse ?? false,
    durationFillMaxConsecutiveRoute:
      project?.durationFillMaxConsecutiveRoute?.toString() ?? "2"
  });

  useEffect(() => {
    if (!showSuccess) {
      return;
    }

    const timer = window.setTimeout(() => setShowSuccess(false), 2400);
    return () => window.clearTimeout(timer);
  }, [showSuccess]);

  const selectedStyleHelp = useMemo(
    () => styleOptions.find((option) => option.value === form.stylePreference)?.description ?? "",
    [form.stylePreference]
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    startTransition(async () => {
      try {
        const targetDurationSec = Number(form.targetDurationSec);
        if (!form.targetDurationSec.trim() || Number.isNaN(targetDurationSec)) {
          throw new Error("请填写有效的目标时长。");
        }
        if (targetDurationSec < 5) {
          throw new Error("目标时长不能小于 5 秒。");
        }
        const durationFillMaxConsecutiveRoute = Number(
          form.durationFillMaxConsecutiveRoute
        );
        if (
          !form.durationFillMaxConsecutiveRoute.trim() ||
          Number.isNaN(durationFillMaxConsecutiveRoute)
        ) {
          throw new Error("请填写有效的同地点连续镜头上限。");
        }
        if (
          durationFillMaxConsecutiveRoute < 1 ||
          durationFillMaxConsecutiveRoute > 8
        ) {
          throw new Error("同地点连续镜头上限建议填写 1-8。");
        }

        const payload: ProjectPayload = {
          ...form,
          targetDurationSec,
          durationFillMaxConsecutiveRoute,
          styleNotes: form.styleNotes.trim(),
          status: "draft"
        };

        if (mode === "create") {
          const created = await createProject(payload);
          router.push(`/projects/${created.id}/assets`);
          return;
        }

        if (project) {
          const updated = await updateProject(project.id, payload);
          setForm({
            name: updated.name,
            destination: updated.destination,
            platform: updated.platform,
            targetDurationSec: updated.targetDurationSec.toString(),
            videoType: updated.videoType,
            stylePreference: updated.stylePreference,
            styleNotes: updated.styleNotes,
            routeText: updated.routeText,
            mediaRoot: updated.mediaRoot,
            jianyingDraftRoot: updated.jianyingDraftRoot ?? "",
            status: updated.status,
            validateLocationOrder: updated.validateLocationOrder,
            allowAssetReuse: updated.allowAssetReuse,
            durationFillMaxConsecutiveRoute:
              updated.durationFillMaxConsecutiveRoute.toString()
          });
          setShowSuccess(true);
        }
      } catch (submitError) {
        setError(
          submitError instanceof Error
            ? `保存失败：${submitError.message}`
            : "保存失败，请稍后再试。"
        );
      }
    });
  }

  return (
    <>
      <BlockingNotice
        visible={isPending}
        title={mode === "create" ? "正在创建项目" : "正在保存项目"}
        description="正在同步最新内容，请稍等片刻。"
      />
      <ToastNotice visible={showSuccess} title="保存成功" message="项目内容已经更新。" />

      <div className={embedded ? undefined : "surface-panel p-6 md:p-7"}>
        {!embedded ? (
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-ink">项目基本信息</h2>
            <p className="mt-2 text-sm leading-6 text-ink/70">
              这一页只处理项目基础配置。创建完成后再进入素材录入，保持输入专注。
            </p>
          </div>
        ) : null}

        <form className="grid gap-5 md:grid-cols-2" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">项目名称</span>
            <input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="例如：阿勒泰雪国片"
              className="input-field"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">发布平台</span>
            <select
              value={form.platform}
              onChange={(event) => setForm({ ...form, platform: event.target.value })}
              className="input-field"
            >
              {platformOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">目的地</span>
            <input
              required
              value={form.destination}
              onChange={(event) => setForm({ ...form, destination: event.target.value })}
              placeholder="例如：阿勒泰"
              className="input-field"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">目标时长（秒）</span>
            <input
              required
              type="text"
              inputMode="numeric"
              value={form.targetDurationSec}
              onChange={(event) => {
                const nextValue = event.target.value;
                if (nextValue === "" || /^\d*$/.test(nextValue)) {
                  setForm({ ...form, targetDurationSec: nextValue });
                }
              }}
              placeholder="例如：15"
              className="input-field"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">视频类型</span>
            <select
              value={form.videoType}
              onChange={(event) => setForm({ ...form, videoType: event.target.value })}
              className="input-field"
            >
              {videoTypeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">素材根目录</span>
            <input
              required
              value={form.mediaRoot}
              onChange={(event) => setForm({ ...form, mediaRoot: event.target.value })}
              placeholder="例如：D:\\素材库\\阿勒泰项目"
              className="input-field"
            />
          </label>
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm text-ink/75">风格偏好</span>
            <select
              value={form.stylePreference}
              onChange={(event) => setForm({ ...form, stylePreference: event.target.value })}
              className="input-field"
            >
              {styleOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-ink/55">{selectedStyleHelp}</p>
          </label>
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm text-ink/75">风格补充说明</span>
            <input
              value={form.styleNotes}
              onChange={(event) => setForm({ ...form, styleNotes: event.target.value })}
              placeholder="可选，例如：冷蓝色调、旁白克制、以空镜和回望人物为主"
              className="input-field"
            />
            <p className="mt-2 text-xs text-ink/55">
              可以补充色调、旁白语气、镜头组织方式等细节偏好。
            </p>
          </label>
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm text-ink/75">路线 / 区域（可选）</span>
            <textarea
              value={form.routeText}
              onChange={(event) => setForm({ ...form, routeText: event.target.value })}
              placeholder="例如：将军山、喀纳斯、禾木（可写区域范围，供 LLM 理解本次旅行覆盖范围）"
              rows={4}
              className="input-field"
            />
            <p className="mt-2 text-xs text-ink/55">
              主要用于给 LLM 提供区域上下文，生成分镜与文案时会参考；不填也不影响主流程。
            </p>
          </label>
          <label className="flex items-start gap-3 md:col-span-2">
            <input
              type="checkbox"
              checked={form.allowAssetReuse}
              onChange={(event) =>
                setForm({ ...form, allowAssetReuse: event.target.checked })
              }
              className="mt-1 h-4 w-4 rounded border-line text-pine focus:ring-pine/20"
            />
            <span className="text-sm text-ink/75">
              <span className="block font-medium text-ink">允许镜头复用</span>
              <span className="mt-1 block text-xs leading-5 text-ink/55">
                开启后，分镜生成可多次使用同一素材以凑足目标时长；关闭时保持「一素材一分镜」规则（默认）。
              </span>
            </span>
          </label>
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm text-ink/75">
              同地点连续镜头上限
            </span>
            <input
              required
              type="text"
              inputMode="numeric"
              value={form.durationFillMaxConsecutiveRoute}
              onChange={(event) => {
                const nextValue = event.target.value;
                if (nextValue === "" || /^\d*$/.test(nextValue)) {
                  setForm({
                    ...form,
                    durationFillMaxConsecutiveRoute: nextValue
                  });
                }
              }}
              placeholder="默认 2"
              className="input-field"
            />
            <p className="mt-2 text-xs leading-5 text-ink/55">
              默认 2，表示补齐时长时同一地点最多连续插入 2 个镜头。调大后更容易接近目标时长，
              但同一地点会停留更久，路线推进也会变慢。
            </p>
          </label>
          <label className="flex items-start gap-3 md:col-span-2">
            <input
              type="checkbox"
              checked={form.validateLocationOrder}
              onChange={(event) =>
                setForm({ ...form, validateLocationOrder: event.target.checked })
              }
              className="mt-1 h-4 w-4 rounded border-line text-pine focus:ring-pine/20"
            />
            <span className="text-sm text-ink/75">
              <span className="block font-medium text-ink">校验分镜地点顺序</span>
              <span className="mt-1 block text-xs leading-5 text-ink/55">
                开启后，系统会按上方路线/区域的先后次序检查分镜是否出现地点回跳；适合路线纪实类项目。
              </span>
            </span>
          </label>
          {error ? (
            <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay md:col-span-2">
              {error}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-3 md:col-span-2">
            <button type="submit" disabled={isPending} className="btn-primary">
              {isPending ? "保存中..." : submitLabel}
            </button>
            <Link href={backHref} className="btn-secondary">
              返回项目列表
            </Link>
          </div>
        </form>
      </div>
    </>
  );
}
