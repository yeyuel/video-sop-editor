import Link from "next/link";
import { SectionCard } from "@/components/section-card";
import { StoryboardClient } from "@/components/storyboard-client";
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
            <span className="text-ink/75">分镜生成</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Storyboard</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">分镜时间线</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            分镜会绑定素材 ID，并按节拍点生成镜头时长。你也可以在生成后再做人工微调并保存。
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
            title="分镜脚本"
            description="每条分镜都必须绑定素材 ID，导出时会连同标题、标签和文案一起写入结果。"
          >
            <StoryboardClient
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
