import { AssetIntakeClient } from "@/components/asset-intake-client";
import { ProjectPageLayout } from "@/components/project-page-layout";
import { getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type NewAssetPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function NewAssetPage({ params }: NewAssetPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="assets"
      eyebrow="Asset Intake"
      title="录入素材"
      description="左侧扫描 mediaRoot 目录树，选中文件即可预览并自动带入相对路径；支持视频、图片与音频。"
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "录入素材")}
      aside={
        <div className="rounded-2xl border border-ai/15 bg-ai-soft px-4 py-3 text-xs leading-6 text-ink/60">
          <p className="badge-ai mb-1.5 w-fit">AI 工作流</p>
          扫描 → 预览 → 保存 → Vision 预填
        </div>
      }
    >
      <AssetIntakeClient projectId={projectId} mediaRoot={workspace.project.mediaRoot} />
    </ProjectPageLayout>
  );
}
