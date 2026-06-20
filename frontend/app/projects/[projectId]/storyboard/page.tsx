import Link from "next/link";
import { SectionCard } from "@/components/section-card";
import { StoryboardListClient } from "@/components/storyboard-list-client";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

type ProjectStoryboardPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectStoryboardPage({
  params
}: ProjectStoryboardPageProps) {
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
            <span className="text-ink/75">分镜列表</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Storyboard</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">分镜时间线</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            这里先看时间线摘要，确认镜头顺序、素材绑定和功能位。单条镜头的详细编辑已经下沉到独立页面，避免长列表里来回滚动。
          </p>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="storyboard"
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
            title="分镜列表"
            description="列表页只保留关键信息。需要调整镜头内容时，进入单独编辑页逐条保存。"
          >
            <StoryboardListClient
              projectId={projectId}
              initialBundle={{
                segments: workspace.storyboard,
                validation: workspace.storyboardValidation
              }}
              selectedThemeId={workspace.project.selectedThemeId}
              targetDurationSec={workspace.project.targetDurationSec}
              beatMode={workspace.rhythmPlan.beatMode}
              selectedTrackName={workspace.rhythmPlan.selectedTrackName}
            />
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
