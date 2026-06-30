import Link from "next/link";

import { AssetListClient } from "@/components/asset-list-client";
import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { getWorkspace } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type ProjectAssetsPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectAssetsPage({ params }: ProjectAssetsPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspace(projectId);

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="assets"
      eyebrow="Assets"
      title="素材列表"
      description="项目素材池：支持目录扫描录入、编辑、Vision 预填与删除。"
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "素材列表")}
      topbarAction={{ label: "录入素材", href: `/projects/${projectId}/assets/new` }}
    >
      <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <SectionCard
          title="项目侧配置"
          description="素材根目录挂在项目上，单条素材只需保存相对路径。"
        >
          <div className="space-y-3">
            <div className="surface-muted p-4">
              <p className="text-sm text-ink/50">素材根目录</p>
              <p className="mt-2 break-all text-sm font-medium text-ink">
                {workspace.project.mediaRoot || "未配置"}
              </p>
            </div>
            <div className="rounded-2xl border border-line bg-white p-4">
              <p className="text-sm text-ink/50">路线 / 区域</p>
              <p className="mt-2 text-sm font-medium text-ink">
                {workspace.project.routeText || "未填写（可选，供 LLM 参考）"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href={`/projects/${projectId}/assets/new`} className="btn-primary">
                扫描目录并录入
              </Link>
              <Link href={`/projects/${projectId}`} className="btn-secondary">
                返回项目页
              </Link>
            </div>
          </div>
        </SectionCard>

        <SectionCard title="素材清单" description="点击条目进入编辑，支持 AI 视频分析预填。">
          <AssetListClient projectId={projectId} initialAssets={workspace.assets} />
        </SectionCard>
      </div>
    </ProjectPageLayout>
  );
}
