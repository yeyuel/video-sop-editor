import { ExportPlanClient } from "@/components/export-plan-client";
import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type ProjectExportPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectExportPage({ params }: ProjectExportPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="export"
      eyebrow="Export"
      title="导出信息与脚本预览"
      description="支持 Markdown、JSON、YAML、CSV 预览，含时间线脚本与发布文案。"
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "导出")}
    >
      <SectionCard
        title="导出配置"
        description="导出结果包含时间线脚本、校验摘要和发布文案。"
      >
        <ExportPlanClient
          projectId={projectId}
          initialPlan={workspace.exportPlan}
          storyboardValidation={workspace.storyboardValidation}
          exportValidation={workspace.exportValidation}
        />
      </SectionCard>
    </ProjectPageLayout>
  );
}
