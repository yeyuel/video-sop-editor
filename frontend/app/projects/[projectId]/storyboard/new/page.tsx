import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { StoryboardSegmentEditorClient } from "@/components/storyboard-segment-editor-client";
import { getStoryboardBeatModeLabel } from "@/lib/storyboard-options";
import { resolveSnapBeatPointsForSegment } from "@/lib/storyboard-beat-points";
import { getWorkspace } from "@/lib/api";
import { storyboardSubBreadcrumbs } from "@/lib/project-nav";
import type { StoryboardSegment } from "@/types/domain";

type ProjectStoryboardNewPageProps = {
  params: Promise<{
    projectId: string;
  }>;
  searchParams: Promise<{
    after?: string;
  }>;
};

function sliceBeatPoints(beatPoints: number[], startTime: number, endTime: number) {
  const scoped = beatPoints.filter((point) => point >= startTime && point <= endTime);
  return scoped.length > 0 ? scoped : [startTime, endTime];
}

export default async function ProjectStoryboardNewPage({
  params,
  searchParams
}: ProjectStoryboardNewPageProps) {
  const { projectId } = await params;
  const { after } = await searchParams;
  const workspace = await getWorkspace(projectId);
  const referenceSegment = after
    ? workspace.storyboard.find((segment) => segment.id === after)
    : undefined;
  const lastSegment = workspace.storyboard[workspace.storyboard.length - 1];
  const startTime = referenceSegment?.endTime ?? lastSegment?.endTime ?? 0;
  const defaultDuration = Math.max(
    1,
    Number(
      (
        (referenceSegment?.endTime ?? startTime + 1) -
        (referenceSegment?.startTime ?? startTime)
      ).toFixed(2)
    )
  );
  const endTime = Number((startTime + defaultDuration).toFixed(2));
  const beatMode =
    workspace.rhythmPlan.beatMode !== "none"
      ? workspace.rhythmPlan.beatMode
      : referenceSegment?.beatMode ?? "beat_1";
  const snapBeatPoints = resolveSnapBeatPointsForSegment(
    workspace.rhythmPlan,
    beatMode,
    workspace.project.targetDurationSec
  );

  const initialSegment: StoryboardSegment = {
    id: "",
    startTime,
    endTime,
    assetId: "",
    shotDescription: "",
    function: "",
    rhythm: referenceSegment?.rhythm ?? "balanced",
    beatMode,
    beatPoints: sliceBeatPoints(snapBeatPoints, startTime, endTime),
    subtitle: "",
    attentionRole: referenceSegment?.attentionRole ?? "",
    visualStrength: referenceSegment?.visualStrength ?? "",
    motionPolicy: referenceSegment?.motionPolicy ?? "",
    transitionPolicy: referenceSegment?.transitionPolicy ?? "",
    subtitlePolicy: referenceSegment?.subtitlePolicy ?? "",
    selectionTrace: "",
    voiceoverText: "",
    voiceoverRole: referenceSegment?.voiceoverRole ?? "",
    voiceoverTiming: referenceSegment?.voiceoverTiming ?? "follow_segment"
  };

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="storyboard"
      eyebrow="Storyboard Insert"
      title="新增一条分镜"
      description={
        referenceSegment
          ? "这条新分镜会插入到当前参考镜头之后，保存后系统会自动重排后续时间线。"
          : "这里用于手工新增第一条或补充一条分镜，保存后会自动回到分镜列表。"
      }
      breadcrumbs={storyboardSubBreadcrumbs(projectId, workspace.project.name, "新增分镜")}
      aside={<span className="badge">手工录入</span>}
    >
      <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <SectionCard
          title="新增镜头"
          description="默认时间和节拍模式已预填，你可以重点补素材、描述、功能标签和字幕。"
        >
          <StoryboardSegmentEditorClient
            mode="create"
            assets={workspace.assets}
            projectId={projectId}
            rhythmBeatPoints={snapBeatPoints}
            segment={initialSegment}
            targetDurationSec={workspace.project.targetDurationSec}
            themeId={workspace.project.selectedThemeId}
            afterSegmentId={referenceSegment?.id}
            backHref={`/projects/${projectId}/storyboard`}
          />
        </SectionCard>

        <SectionCard title="插入参考" description="新增动作会尽量保持当前时间线节奏连续。">
          <div className="space-y-3">
            <div className="stat-cell">
              插入位置：
              {referenceSegment
                ? ` 在镜头 ${referenceSegment.id} 之后`
                : " 作为当前列表中的新增镜头"}
            </div>
            <div className="stat-cell">
              默认时间：{initialSegment.startTime}s – {initialSegment.endTime}s
            </div>
            <div className="stat-cell">
              默认节拍模式：{getStoryboardBeatModeLabel(initialSegment.beatMode)}
            </div>
          </div>
        </SectionCard>
      </div>
    </ProjectPageLayout>
  );
}
