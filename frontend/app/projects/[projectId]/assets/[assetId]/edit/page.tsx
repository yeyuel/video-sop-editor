import { AssetFormPrototype } from "@/components/asset-form-prototype";
import { ProjectPageLayout } from "@/components/project-page-layout";
import { getAsset, getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type EditAssetPageProps = {
  params: Promise<{
    projectId: string;
    assetId: string;
  }>;
};

export default async function EditAssetPage({ params }: EditAssetPageProps) {
  const { projectId, assetId } = await params;
  const [asset, workspace] = await Promise.all([
    getAsset(projectId, assetId),
    getWorkspace(projectId)
  ]);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="assets"
      eyebrow="Edit Asset"
      title="编辑素材"
      description={`素材 ${asset.assetId}：保存后停留本页，可直接 AI 分析或使用「保存并 AI 分析」。`}
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "编辑素材")}
      aside={<span className="badge-ai">Vision 预填</span>}
    >
      <AssetFormPrototype
        key={`${asset.assetId}-${asset.visionAnalysisStatus}-${(asset.visionPrefilledFields ?? []).join(",")}`}
        mode="edit"
        projectId={projectId}
        asset={asset}
      />
    </ProjectPageLayout>
  );
}
