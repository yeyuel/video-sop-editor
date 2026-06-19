import Link from "next/link";
import { AssetFormPrototype } from "@/components/asset-form-prototype";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkspace } from "@/lib/api";
import { getCompletedWorkflowSteps, getEnabledWorkflowSteps } from "@/lib/workflow";

type NewAssetPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function NewAssetPage({ params }: NewAssetPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <main className="pb-12">
      <Topbar />
      <div className="mx-auto max-w-7xl px-6">
        <div className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
          <div className="mb-4 flex flex-wrap items-center gap-2 text-sm text-ink/55">
            <Link href="/" className="transition hover:text-pine">
              首页
            </Link>
            <span>/</span>
            <Link href={`/projects/${projectId}`} className="transition hover:text-pine">
              项目页
            </Link>
            <span>/</span>
            <Link href={`/projects/${projectId}/assets`} className="transition hover:text-pine">
              素材列表
            </Link>
            <span>/</span>
            <span className="text-ink/75">新增素材</span>
          </div>
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">New Asset</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">新增素材</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            素材表单单独占一页，你可以直接返回素材列表、项目页或首页。
          </p>
        </div>

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

        <div className="mt-6">
          <AssetFormPrototype mode="create" projectId={projectId} />
        </div>
      </div>
    </main>
  );
}
