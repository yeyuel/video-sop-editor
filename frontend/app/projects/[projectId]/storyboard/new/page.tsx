import Link from "next/link";
import { SectionCard } from "@/components/section-card";
import { StoryboardSegmentEditorClient } from "@/components/storyboard-segment-editor-client";
import { getStoryboardBeatModeLabel } from "@/lib/storyboard-options";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";
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

  const initialSegment: StoryboardSegment = {
    id: "",
    startTime,
    endTime,
    assetId: "",
    shotDescription: "",
    function: "",
    rhythm: referenceSegment?.rhythm ?? "balanced",
    beatMode:
      workspace.rhythmPlan.beatMode !== "none"
        ? workspace.rhythmPlan.beatMode
        : referenceSegment?.beatMode ?? "beat_1",
    beatPoints: sliceBeatPoints(workspace.rhythmPlan.beatPoints, startTime, endTime),
    subtitle: ""
  };

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
            <Link href={`/projects/${projectId}/storyboard`} className="transition hover:text-pine">
              分镜列表
            </Link>
            <span>/</span>
            <span className="text-ink/75">新增分镜</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Storyboard Insert</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">新增一条分镜</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            {referenceSegment
              ? "这条新分镜会插入到当前参考镜头之后，保存后系统会自动重排后续时间线。"
              : "这里用于手工新增第一条或补充一条分镜，保存后会自动回到分镜列表。"}
          </p>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="storyboard"
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

        <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <SectionCard
            title="新增镜头"
            description="默认时间和节拍模式已预填，你可以重点补素材、描述、功能标签和字幕。"
          >
            <StoryboardSegmentEditorClient
              mode="create"
              assets={workspace.assets}
              projectId={projectId}
              segment={initialSegment}
              targetDurationSec={workspace.project.targetDurationSec}
              themeId={workspace.project.selectedThemeId}
              afterSegmentId={referenceSegment?.id}
              backHref={`/projects/${projectId}/storyboard`}
            />
          </SectionCard>

          <SectionCard
            title="插入参考"
            description="新增动作会尽量保持当前时间线节奏连续。"
          >
            <div className="space-y-3">
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                插入位置：
                {referenceSegment
                  ? ` 在镜头 ${referenceSegment.id} 之后`
                  : " 作为当前列表中的新增镜头"}
              </div>
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                默认时间：{initialSegment.startTime}s - {initialSegment.endTime}s
              </div>
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                默认节拍模式：{getStoryboardBeatModeLabel(initialSegment.beatMode)}
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
