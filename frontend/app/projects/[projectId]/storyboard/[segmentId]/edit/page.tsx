import Link from "next/link";
import { SectionCard } from "@/components/section-card";
import { StoryboardSegmentEditorClient } from "@/components/storyboard-segment-editor-client";
import {
  getStoryboardBeatModeLabel,
  getStoryboardFunctionLabel
} from "@/lib/storyboard-options";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getStoryboardSegment, getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

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
            <span className="text-ink/75">镜头编辑</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Storyboard Detail</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">编辑单条分镜</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            这里处理单个镜头的详细信息。保存只作用于当前镜头，不会覆盖整条时间线里的其他内容。
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
            title="镜头编辑"
            description="可以修改时间、素材、描述、功能位、字幕和当前镜头的节拍点。"
          >
            <StoryboardSegmentEditorClient
              assets={workspace.assets}
              projectId={projectId}
              segment={segment}
              targetDurationSec={workspace.project.targetDurationSec}
              backHref={`/projects/${projectId}/storyboard`}
            />
          </SectionCard>

          <SectionCard
            title="当前镜头摘要"
            description="先看重点信息，再决定是否需要进一步改动。"
          >
            <div className="space-y-3">
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                镜头 ID：{segment.id}
              </div>
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                时间范围：{segment.startTime}s - {segment.endTime}s
              </div>
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                素材 ID：{segment.assetId}
              </div>
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                功能标签：{getStoryboardFunctionLabel(segment.function)}
              </div>
              <div className="rounded-2xl bg-sand/60 px-4 py-3 text-sm text-ink/70">
                节拍模式：{getStoryboardBeatModeLabel(segment.beatMode)}
              </div>
            </div>
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
