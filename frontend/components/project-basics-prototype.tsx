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
  backHref = "/"
}: ProjectBasicsPrototypeProps) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);
  const [form, setForm] = useState<ProjectPayload>({
    name: project?.name ?? "",
    destination: project?.destination ?? "",
    platform: project?.platform ?? "xiaohongshu",
    targetDurationSec: project?.targetDurationSec ?? 60,
    videoType: project?.videoType ?? "emotion_film",
    stylePreference: project?.stylePreference ?? styleOptions[0].value,
    styleNotes: project?.styleNotes ?? "",
    routeText: project?.routeText ?? "",
    mediaRoot: project?.mediaRoot ?? "",
    status: project?.status ?? "draft"
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
        const payload: ProjectPayload = {
          ...form,
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
            targetDurationSec: updated.targetDurationSec,
            videoType: updated.videoType,
            stylePreference: updated.stylePreference,
            styleNotes: updated.styleNotes,
            routeText: updated.routeText,
            mediaRoot: updated.mediaRoot,
            status: updated.status
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

      <div className="rounded-xl2 border border-black/5 bg-white/90 p-6 shadow-card backdrop-blur">
        <div className="mb-6">
          <h2 className="text-2xl font-semibold text-ink">项目基本信息</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            这一页只处理项目基础配置。创建完成后再进入素材录入，保持输入专注。
          </p>
        </div>

        <form className="grid gap-5 md:grid-cols-2" onSubmit={handleSubmit}>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">项目名称</span>
            <input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
              placeholder="例如：阿勒泰雪国片"
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">发布平台</span>
            <select
              value={form.platform}
              onChange={(event) => setForm({ ...form, platform: event.target.value })}
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">目标时长（秒）</span>
            <input
              required
              min={10}
              type="number"
              value={form.targetDurationSec}
              onChange={(event) =>
                setForm({ ...form, targetDurationSec: Number(event.target.value) })
              }
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
            />
          </label>
          <label className="block">
            <span className="mb-2 block text-sm text-ink/75">视频类型</span>
            <select
              value={form.videoType}
              onChange={(event) => setForm({ ...form, videoType: event.target.value })}
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
            />
          </label>
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm text-ink/75">风格偏好</span>
            <select
              value={form.stylePreference}
              onChange={(event) => setForm({ ...form, stylePreference: event.target.value })}
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
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
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
            />
            <p className="mt-2 text-xs text-ink/55">
              可以补充色调、旁白语气、镜头组织方式等细节偏好。
            </p>
          </label>
          <label className="block md:col-span-2">
            <span className="mb-2 block text-sm text-ink/75">路线</span>
            <textarea
              required
              value={form.routeText}
              onChange={(event) => setForm({ ...form, routeText: event.target.value })}
              placeholder="例如：将军山 - 喀纳斯 - 禾木"
              rows={4}
              className="w-full rounded-2xl border border-pine/30 bg-white px-4 py-3 outline-none transition focus:border-pine"
            />
          </label>
          {error ? (
            <div className="rounded-2xl border border-clay/15 bg-[#fff5ef] px-4 py-3 text-sm text-clay md:col-span-2">
              {error}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-3 md:col-span-2">
            <button
              type="submit"
              disabled={isPending}
              className="inline-flex rounded-full bg-pine px-5 py-3 text-sm font-medium text-white transition hover:bg-pine/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isPending ? "保存中..." : submitLabel}
            </button>
            <Link
              href={backHref}
              className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist"
            >
              返回项目列表
            </Link>
          </div>
        </form>
      </div>
    </>
  );
}
