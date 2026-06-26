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
            先用 LLM 推荐 2–3 首真实 BGM，选定后下载上传，完成节拍识别后才能进入分镜。
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
            description="LLM 推荐真实歌名与搜索提示；下载上传 BGM 后自动识别节拍点。"
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
