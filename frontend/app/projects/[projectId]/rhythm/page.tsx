import { ProjectPageLayout } from "@/components/project-page-layout";
import { RhythmPlanClient } from "@/components/rhythm-plan-client";
import { SectionCard } from "@/components/section-card";
import { getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type ProjectRhythmPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectRhythmPage({ params }: ProjectRhythmPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="rhythm"
      eyebrow="Rhythm"
      title="节奏规划"
      description="LLM 推荐 BGM，上传后自动识别节拍点，为分镜对齐提供基础。"
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "节奏")}
      aside={<span className="badge-ai">LLM + 音频分析</span>}
    >
      <SectionCard
        title="节奏与音乐方案"
        description="推荐真实歌名与搜索提示；下载上传 BGM 后自动识别节拍点。"
      >
        <RhythmPlanClient
          projectId={projectId}
          targetDurationSec={workspace.project.targetDurationSec}
          initialPlan={workspace.rhythmPlan}
        />
      </SectionCard>
    </ProjectPageLayout>
  );
}
