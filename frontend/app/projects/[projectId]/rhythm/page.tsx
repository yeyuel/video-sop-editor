import Link from "next/link";
import { RhythmPlanClient } from "@/components/rhythm-plan-client";
import { SectionCard } from "@/components/section-card";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

type ProjectRhythmPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectRhythmPage({ params }: ProjectRhythmPageProps) {
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
            <span className="text-ink/75">节奏规划</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Rhythm</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">节奏规划</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            这一阶段输出节拍点、暗场建议和节奏说明。后面的分镜时间线会直接依赖这些卡点数据。
          </p>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="rhythm"
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
            title="节奏与音乐方案"
            description="这里不只是推荐歌名，而是把节奏规划成后续可执行的 beat points。"
          >
            <RhythmPlanClient
              projectId={projectId}
              targetDurationSec={workspace.project.targetDurationSec}
              initialPlan={workspace.rhythmPlan}
            />
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
