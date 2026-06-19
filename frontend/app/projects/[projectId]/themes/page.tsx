import Link from "next/link";
import { SectionCard } from "@/components/section-card";
import { ThemeSelectorClient } from "@/components/theme-selector-client";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

type ProjectThemesPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectThemesPage({ params }: ProjectThemesPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <main className="pb-12">
      <Topbar />
      <div className="mx-auto max-w-7xl px-6">
        <section className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-ink/55">
            <Link href="/" className="transition hover:text-pine">
              首页
            </Link>
            <span>/</span>
            <Link href={`/projects/${projectId}`} className="transition hover:text-pine">
              项目页
            </Link>
            <span>/</span>
            <span className="text-ink/75">主题生成</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Theme</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">主题生成与确认</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            先确定叙事方向，再进入节奏规划和分镜生成，避免只按素材堆叠时间线。
          </p>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="theme"
            enabledSteps={getEnabledWorkflowSteps(workspace)}
            completedSteps={getCompletedWorkflowSteps(workspace)}
            hrefMap={{
              create: `/projects/${projectId}`,
              assets: `/projects/${projectId}/assets`,
              theme: `/projects/${projectId}/themes`,
              rhythm: `/projects/${projectId}/rhythm`,
              storyboard: `/projects/${projectId}/storyboard`,
              export: `/projects/${projectId}/export`
            }}
          />
        </div>

        <div className="mt-6">
          <SectionCard
            title="主题候选"
            description="系统会基于当前项目基础信息和已录入素材生成多个叙事方向。你需要先选定一个主主题。"
          >
            <ThemeSelectorClient projectId={projectId} initialThemes={workspace.themes} />
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
