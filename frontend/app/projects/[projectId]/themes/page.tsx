import Link from "next/link";

import { ProjectPageLayout } from "@/components/project-page-layout";
import { SectionCard } from "@/components/section-card";
import { ThemeSelectorClient } from "@/components/theme-selector-client";
import { Topbar } from "@/components/topbar";
import { getWorkspaceStrict } from "@/lib/api";
import { projectBreadcrumbs } from "@/lib/project-nav";

type ProjectThemesPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function ProjectThemesPage({ params }: ProjectThemesPageProps) {
  const { projectId } = await params;
  const workspace = await getWorkspaceStrict(projectId);

  if (!workspace) {
    return (
      <main className="pb-14">
        <Topbar />
        <div className="mx-auto max-w-7xl px-6">
          <section className="surface-panel border-clay/20 bg-[#FFF7F3] p-6 text-sm leading-7 text-clay">
            <h2 className="text-lg font-semibold">无法加载项目数据</h2>
            <p className="mt-2">
              后端未找到项目 <code>{projectId}</code>。请回到{" "}
              <Link href="/" className="text-pine underline">
                首页
              </Link>{" "}
              重新进入。
            </p>
          </section>
        </div>
      </main>
    );
  }

  return (
    <ProjectPageLayout
      projectId={projectId}
      workspace={workspace}
      currentStep="theme"
      eyebrow="Theme"
      title="主题生成与确认"
      description="先确定叙事方向，再进入节奏规划和分镜生成，避免只按素材堆叠时间线。"
      breadcrumbs={projectBreadcrumbs(projectId, workspace.project.name, "主题")}
      aside={<span className="badge-ai">LLM 生成</span>}
    >
      <SectionCard
        title="主题候选"
        description="基于项目信息与素材生成多个叙事方向，选定一个主主题后继续。"
      >
        <ThemeSelectorClient projectId={projectId} initialThemes={workspace.themes} />
      </SectionCard>
    </ProjectPageLayout>
  );
}
