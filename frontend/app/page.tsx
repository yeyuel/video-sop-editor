import { ProjectHistoryClient } from "@/components/project-history-client";
import { PageShell } from "@/components/page-shell";
import { Topbar } from "@/components/topbar";
import { getProjects, getWorkspace } from "@/lib/api";

export default async function HomePage() {
  const projects = await getProjects();
  const workspaces = await Promise.all(projects.map((project) => getWorkspace(project.id)));

  return (
    <main className="pb-14">
      <Topbar />
      <div className="mx-auto max-w-7xl space-y-6 px-6">
        <PageShell
          eyebrow="Project History"
          title="历史项目列表"
          description="首页只承担项目入口和历史回看。进入项目后，再沿着 workflow 逐步处理素材、主题、节奏、分镜和导出。"
          aside={
            <div className="rounded-2xl border border-line bg-white px-4 py-3 text-sm leading-6 text-ink/55">
              已覆盖：项目 CRUD、素材录入、主题、节奏、分镜、导出
            </div>
          }
        />

        <ProjectHistoryClient projects={projects} workspaces={workspaces} />
      </div>
    </main>
  );
}
