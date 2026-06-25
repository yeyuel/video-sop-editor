"use client";

import Link from "next/link";
import { useMemo, useState, useTransition } from "react";
import { deleteProject } from "@/lib/browser-api";
import { getProjectStage, workflowSteps } from "@/lib/workflow";
import type { Project, WorkspaceData } from "@/types/domain";

type ProjectHistoryClientProps = {
  projects: Project[];
  workspaces: WorkspaceData[];
};

type ProjectStats = Project & {
  assetCount: number;
  stageLabel: string;
};

function buildProjectStats(
  projects: Project[],
  workspaces: WorkspaceData[]
): ProjectStats[] {
  return projects.map((project) => {
    const workspace = workspaces.find((item) => item.project.id === project.id);
    const assetCount = workspace?.assets.length ?? 0;
    const stage = workspace ? getProjectStage(workspace) : "create";

    return {
      ...project,
      assetCount,
      stageLabel: workflowSteps.find((item) => item.id === stage)?.label ?? "新建"
    };
  });
}

export function ProjectHistoryClient({
  projects,
  workspaces
}: ProjectHistoryClientProps) {
  const platformLabelMap: Record<string, string> = {
    xiaohongshu: "小红书",
    douyin: "抖音",
    wechat_channel: "视频号",
    bilibili: "Bilibili"
  };
  const [isPending, startTransition] = useTransition();
  const [projectState, setProjectState] = useState(projects);
  const [workspaceState, setWorkspaceState] = useState(workspaces);
  const [confirmProject, setConfirmProject] = useState<ProjectStats | null>(null);
  const [error, setError] = useState("");

  const projectStats = useMemo(
    () => buildProjectStats(projectState, workspaceState),
    [projectState, workspaceState]
  );

  function openConfirm(project: ProjectStats) {
    setConfirmProject(project);
    setError("");
  }

  function closeConfirm() {
    if (isPending) {
      return;
    }
    setConfirmProject(null);
  }

  function handleDelete() {
    if (!confirmProject) {
      return;
    }

    setError("");
    startTransition(async () => {
      try {
        await deleteProject(confirmProject.id);
        setProjectState((current) =>
          current.filter((project) => project.id !== confirmProject.id)
        );
        setWorkspaceState((current) =>
          current.filter((workspace) => workspace.project.id !== confirmProject.id)
        );
        setConfirmProject(null);
      } catch (submitError) {
        setError(
          submitError instanceof Error ? submitError.message : "删除项目失败，请稍后重试。"
        );
      }
    });
  }

  return (
    <>
      {projectStats.length === 0 ? (
        <div className="rounded-xl2 border border-dashed border-pine/25 bg-white/70 p-8 text-center text-ink/65">
          当前还没有项目。可以先从右上角创建一个新项目。
        </div>
      ) : (
        <div className="space-y-4">
          {projectStats.map((project) => (
            <article
              key={project.id}
              className="grid gap-5 rounded-xl2 border border-black/5 bg-white/90 p-6 shadow-card backdrop-blur lg:grid-cols-[1.4fr_0.9fr]"
            >
              <div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-full bg-mist px-3 py-1 text-xs font-medium text-pine">
                    当前阶段：{project.stageLabel}
                  </span>
                  <span className="text-xs uppercase tracking-[0.22em] text-pine/65">
                    {platformLabelMap[project.platform] ?? project.platform}
                  </span>
                </div>
                <h2 className="mt-3 text-2xl font-semibold text-ink">{project.name}</h2>
                <p className="mt-2 text-sm leading-6 text-ink/70">
                  {project.destination}
                  {project.routeText ? ` · ${project.routeText}` : ""}
                </p>
                <div className="mt-4 grid gap-3 text-sm text-ink/70 md:grid-cols-3">
                  <div className="rounded-2xl bg-sand/70 px-4 py-3">
                    目标时长 {project.targetDurationSec}s
                  </div>
                  <div className="rounded-2xl bg-sand/70 px-4 py-3">
                    已录入素材 {project.assetCount} 条
                  </div>
                  <div className="rounded-2xl bg-sand/70 px-4 py-3">状态 {project.status}</div>
                </div>
              </div>
              <div className="flex flex-col justify-between gap-4 rounded-2xl border border-black/5 bg-sand/45 p-4">
                <div>
                  <p className="text-sm font-medium text-ink">工作台入口</p>
                  <p className="mt-2 text-sm leading-6 text-ink/65">
                    从项目页进入完整 workflow，也可以直接跳到素材列表继续整理素材。
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={`/projects/${project.id}`}
                    className="inline-flex rounded-full bg-pine px-4 py-2 text-sm font-medium text-white transition hover:bg-pine/90"
                  >
                    进入项目
                  </Link>
                  <Link
                    href={`/projects/${project.id}/assets`}
                    className="inline-flex rounded-full border border-pine/20 bg-white px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist"
                  >
                    素材列表
                  </Link>
                  <button
                    type="button"
                    onClick={() => openConfirm(project)}
                    className="inline-flex rounded-full border border-clay/20 bg-white px-4 py-2 text-sm font-medium text-clay transition hover:border-clay/35 hover:bg-[#fff6f2]"
                  >
                    删除项目
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {confirmProject ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/35 px-6">
          <div className="w-full max-w-md rounded-xl2 border border-black/5 bg-white p-6 shadow-card">
            <p className="text-xs uppercase tracking-[0.22em] text-clay/80">Delete Project</p>
            <h3 className="mt-3 text-2xl font-semibold text-ink">确认删除项目？</h3>
            <p className="mt-3 text-sm leading-6 text-ink/70">
              将删除项目“{confirmProject.name}”以及它关联的素材、主题、节奏、分镜和导出数据。
              这个操作无法撤回。
            </p>
            {error ? <p className="mt-3 text-sm text-red-600">{error}</p> : null}
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={handleDelete}
                disabled={isPending}
                className="inline-flex rounded-full bg-clay px-5 py-3 text-sm font-medium text-white transition hover:bg-clay/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isPending ? "删除中..." : "确认删除"}
              </button>
              <button
                type="button"
                onClick={closeConfirm}
                disabled={isPending}
                className="inline-flex rounded-full border border-pine/20 bg-white px-5 py-3 text-sm font-medium text-pine transition hover:bg-mist disabled:cursor-not-allowed disabled:opacity-60"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
