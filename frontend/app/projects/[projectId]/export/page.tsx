import Link from "next/link";
import { ExportPlanClient } from "@/components/export-plan-client";
import { SectionCard } from "@/components/section-card";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

type ProjectExportPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectExportPage({ params }: ProjectExportPageProps) {
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
            <span className="text-ink/75">导出</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Export</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">导出信息与脚本预览</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            当前版本先手动填写标题、标签和文案。后续接入 LLM 建议时，这一层数据结构可以直接复用。
          </p>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="export"
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
            title="导出配置"
            description="支持 Markdown、JSON、YAML、CSV 四种预览格式，导出结果中会包含时间线脚本、校验摘要和发布文案。"
          >
            <ExportPlanClient
              projectId={projectId}
              initialPlan={workspace.exportPlan}
              storyboardValidation={workspace.storyboardValidation}
              exportValidation={workspace.exportValidation}
            />
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
