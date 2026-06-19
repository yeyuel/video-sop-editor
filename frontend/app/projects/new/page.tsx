import { ProjectBasicsPrototype } from "@/components/project-basics-prototype";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";

export default function NewProjectPage() {
  return (
    <main className="pb-12">
      <Topbar />
      <div className="mx-auto max-w-7xl px-6">
        <div className="rounded-xl2 border border-black/5 bg-white/80 p-6 shadow-card backdrop-blur">
          <p className="text-xs uppercase tracking-[0.24em] text-pine/70">Create Project</p>
          <h2 className="mt-3 text-3xl font-semibold text-ink">新建项目</h2>
          <p className="mt-2 text-sm leading-6 text-ink/70">
            第一步只填写项目基础信息，不混入素材和后续阶段内容，保持输入路径清晰。
          </p>
        </div>

        <div className="mt-6">
          <WorkflowStepper currentStep="create" enabledSteps={["create"]} />
        </div>

        <div className="mt-6">
          <ProjectBasicsPrototype mode="create" />
        </div>
      </div>
    </main>
  );
}
