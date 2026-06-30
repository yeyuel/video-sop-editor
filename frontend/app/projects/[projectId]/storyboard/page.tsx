import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { StoryboardListClient } from "@/components/storyboard-list-client";
import { getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type ProjectStoryboardPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectStoryboardPage({ params }: ProjectStoryboardPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="storyboard"
      eyebrow="Storyboard"
      title="分镜时间线"
      description="查看镜头顺序、素材绑定与功能位；详细编辑在独立页面完成。"
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "分镜")}
      aside={<span className="badge-ai">LLM 生成</span>}
    >
      <SectionCard
        title="分镜列表"
        description="列表保留关键信息，逐条进入编辑页调整内容。"
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
    </ProjectPageLayout>
  );
}
