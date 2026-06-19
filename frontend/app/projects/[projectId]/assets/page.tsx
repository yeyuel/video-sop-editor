import Link from "next/link";
import { AssetListClient } from "@/components/asset-list-client";
import { SectionCard } from "@/components/section-card";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

type ProjectAssetsPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectAssetsPage({
  params
}: ProjectAssetsPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <main className="pb-12">
      <Topbar
        action={{
          label: "新增素材",
          href: `/projects/${projectId}/assets/new`
        }}
      />
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
            <span className="text-ink/75">素材列表</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Asset Intake</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">素材列表</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            项目：{workspace.project.name}。素材录入拆成独立列表和表单页，支持直接新增、编辑和删除。
          </p>
        </section>

        <div className="mt-6">
          <WorkflowStepper
            currentStep="assets"
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

        <div className="mt-6 grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
          <SectionCard
            title="项目侧配置"
            description="素材根目录挂在项目上，这样单条素材只需要保存相对路径。"
          >
            <div className="space-y-3">
              <div className="rounded-2xl bg-sand/60 p-4">
                <p className="text-sm text-ink/60">素材根目录</p>
                <p className="mt-2 break-all text-sm font-medium text-ink">
                  {workspace.project.mediaRoot || "未配置"}
                </p>
              </div>
              <div className="rounded-2xl bg-white p-4">
                <p className="text-sm text-ink/60">路线</p>
                <p className="mt-2 text-sm font-medium text-ink">{workspace.project.routeText}</p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/"
                  className="inline-flex rounded-full border border-pine/20 bg-white px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist"
                >
                  返回首页
                </Link>
                <Link
                  href={`/projects/${projectId}`}
                  className="inline-flex rounded-full border border-pine/20 bg-white px-4 py-2 text-sm font-medium text-pine transition hover:bg-mist"
                >
                  返回项目页
                </Link>
                <Link
                  href={`/projects/${projectId}/assets/new`}
                  className="inline-flex rounded-full bg-pine px-4 py-2 text-sm font-medium text-white transition hover:bg-pine/90"
                >
                  录入新素材
                </Link>
              </div>
            </div>
          </SectionCard>

          <SectionCard
            title="素材清单"
            description="当前页可以直接回首页，不需要先跳回项目页。"
          >
            <AssetListClient projectId={projectId} initialAssets={workspace.assets} />
          </SectionCard>
        </div>
      </div>
    </main>
  );
}
