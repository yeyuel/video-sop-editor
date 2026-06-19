import { ProjectBasicsPrototype } from "@/components/project-basics-prototype";
import { SectionCard } from "@/components/section-card";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import {
  getCompletedWorkflowSteps,
  getEnabledWorkflowSteps,
  workflowSteps
} from "@/lib/workflow";
import { getWorkspace } from "@/lib/api";

type ProjectPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectWorkspacePage({ params }: ProjectPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);
  const enabledSteps = getEnabledWorkflowSteps(workspace);
  const completedSteps = getCompletedWorkflowSteps(workspace);

  return (
    <main className="pb-12">
      <Topbar />
      <div className="mx-auto max-w-7xl px-6">
        <section className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Project Workspace</p>
          <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-3xl font-semibold text-ink">{workspace.project.name}</h2>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                {workspace.project.destination} · {workspace.project.routeText}
              </p>
            </div>
            <div className="rounded-2xl bg-sand/70 px-4 py-3 text-sm text-ink/70">
              当前完成：{completedSteps.length}/{workflowSteps.length} 个阶段
            </div>
          </div>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="create"
            enabledSteps={enabledSteps}
            completedSteps={completedSteps}
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

        <div className="mt-6 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <ProjectBasicsPrototype
            mode="edit"
            project={workspace.project}
            submitLabel="保存项目"
            backHref="/"
          />

          <div className="space-y-6">
            <SectionCard
              title="当前数据状态"
              description="导航已经收敛到上方 stepper，这里只保留数据状态，便于快速确认每个业务对象是否已经落库。"
            >
              <div className="grid gap-3 text-sm text-ink/70 md:grid-cols-2">
                <div className="rounded-2xl bg-sand/60 px-4 py-3">素材数量：{workspace.assets.length}</div>
                <div className="rounded-2xl bg-sand/60 px-4 py-3">
                  主题数量：{workspace.themes.length}
                </div>
                <div className="rounded-2xl bg-sand/60 px-4 py-3">
                  节拍点：{workspace.rhythmPlan.beatPoints.length}
                </div>
                <div className="rounded-2xl bg-sand/60 px-4 py-3">
                  分镜段数：{workspace.storyboard.length}
                </div>
                <div className="rounded-2xl bg-sand/60 px-4 py-3 md:col-span-2">
                  导出标题：{workspace.exportPlan.title || "未填写"}
                </div>
              </div>
            </SectionCard>
          </div>
        </div>
      </div>
    </main>
  );
}
