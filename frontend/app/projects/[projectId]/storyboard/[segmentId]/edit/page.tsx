import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { StoryboardSegmentEditorClient } from "@/components/storyboard-segment-editor-client";
import {
  getStoryboardBeatModeLabel,
  getStoryboardFunctionLabel
} from "@/lib/storyboard-options";
import { resolveSnapBeatPointsForSegment } from "@/lib/storyboard-beat-points";
import { getStoryboardSegment, getWorkspace } from "@/lib/api";
import { storyboardSubBreadcrumbs } from "@/lib/project-nav";

type ProjectStoryboardEditPageProps = {
  params: Promise<{
    projectId: string;
    segmentId: string;
  }>;
};

export default async function ProjectStoryboardEditPage({
  params
}: ProjectStoryboardEditPageProps) {
  const { projectId, segmentId } = await params;
  const [workspace, segment] = await Promise.all([
    getWorkspace(projectId),
    getStoryboardSegment(projectId, segmentId)
  ]);
  const snapBeatPoints = resolveSnapBeatPointsForSegment(
    workspace.rhythmPlan,
    segment.beatMode,
    workspace.project.targetDurationSec
  );

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="storyboard"
      eyebrow="Storyboard Detail"
      title="编辑单条分镜"
      description="这里处理单个镜头的详细信息。保存只作用于当前镜头，不会覆盖整条时间线里的其他内容。"
      breadcrumbs={storyboardSubBreadcrumbs(projectId, workspace.project.name, "镜头编辑")}
      aside={<span className="stat-pill">镜头 {segment.id}</span>}
    >
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard
          title="镜头编辑"
          description="可以修改时间、素材、描述、功能位、字幕和当前镜头的节拍点。"
        >
          <StoryboardSegmentEditorClient
            assets={workspace.assets}
            projectId={projectId}
            rhythmBeatPoints={snapBeatPoints}
            segment={segment}
            targetDurationSec={workspace.project.targetDurationSec}
            backHref={`/projects/${projectId}/storyboard`}
          />
        </SectionCard>

        <SectionCard title="当前镜头摘要" description="先看重点信息，再决定是否需要进一步改动。">
          <div className="space-y-3">
            <div className="stat-cell">镜头 ID：{segment.id}</div>
            <div className="stat-cell">
              时间范围：{segment.startTime}s – {segment.endTime}s
            </div>
            <div className="stat-cell">素材 ID：{segment.assetId}</div>
            <div className="stat-cell">功能标签：{getStoryboardFunctionLabel(segment.function)}</div>
            <div className="stat-cell">节拍模式：{getStoryboardBeatModeLabel(segment.beatMode)}</div>
          </div>
        </SectionCard>
      </div>
    </ProjectPageLayout>
  );
}
