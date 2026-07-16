import { ProjectBasicsPrototype } from "@/components/project-basics-prototype";
import { RoughCutLauncher } from "@/components/rough-cut-launcher";
import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";
import { getCompletedWorkflowSteps, workflowSteps } from "@/lib/workflow";

type ProjectPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectWorkspacePage({ params }: ProjectPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);
  const completedSteps = getCompletedWorkflowSteps(workspace);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="create"
      eyebrow="Project Workspace"
      title={workspace.project.name}
      description={`${workspace.project.destination}${workspace.project.routeText ? ` · ${workspace.project.routeText}` : ""}`}
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "项目概览")}
      aside={
        <span className="stat-pill">
          {completedSteps.length}/{workflowSteps.length} 阶段完成
        </span>
      }
    >
      <RoughCutLauncher projectId={projectId} assetCount={workspace.assets.length} />
      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <SectionCard
          title="项目基本信息"
          description="修改目的地、时长、风格偏好与素材根目录等基础配置。"
        >
          <ProjectBasicsPrototype
            embedded
            mode="edit"
            project={workspace.project}
            submitLabel="保存项目"
            backHref="/"
          />
        </SectionCard>

        <SectionCard
          title="当前数据状态"
          description="快速确认各业务对象是否已落库。"
        >
          <div className="grid gap-3 text-sm text-ink/65 md:grid-cols-2">
            <div className="stat-cell">素材：{workspace.assets.length}</div>
            <div className="stat-cell">主题：{workspace.themes.length}</div>
            <div className="stat-cell">节拍点：{workspace.rhythmPlan.beatPoints.length}</div>
            <div className="stat-cell">分镜：{workspace.storyboard.length}</div>
            <div className="stat-cell md:col-span-2">
              导出标题：{workspace.exportPlan.title || "未填写"}
            </div>
          </div>
        </SectionCard>
      </div>
    </ProjectPageLayout>
  );
}
