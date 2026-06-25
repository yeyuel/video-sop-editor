import { ProjectHistoryClient } from "@/components/project-history-client";
import { Topbar } from "@/components/topbar";
import { getProjects, getWorkspace } from "@/lib/api";

export default async function HomePage() {
  const projects = await getProjects();
  const workspaces = await Promise.all(projects.map((project) => getWorkspace(project.id)));

  return (
    <main className="pb-12">
      <Topbar />
      <div className="mx-auto max-w-7xl px-6">
        <section className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-pine/70">
                Project History
              </p>
              <h2 className="mt-2 text-2xl font-semibold text-ink">历史项目列表</h2>
              <p className="mt-2 text-sm leading-6 text-ink/70">
                首页只承担项目入口和历史回看。进入项目后，再沿着 workflow 逐步处理素材、主题、节奏、分镜和导出。
              </p>
            </div>
            <div className="rounded-2xl bg-sand/70 px-4 py-3 text-sm text-ink/70">
              当前版本已覆盖：项目 CRUD、素材 CRUD、主题选择、节奏规划、分镜生成、导出预览
            </div>
          </div>
        </section>

        <div className="mt-6">
          <ProjectHistoryClient projects={projects} workspaces={workspaces} />
        </div>
      </div>
    </main>
  );
}
