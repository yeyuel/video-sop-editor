import { PageShell } from "@/components/page-shell";
import { ProjectBasicsPrototype } from "@/components/project-basics-prototype";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";

export default function NewProjectPage() {
  return (
    <main className="pb-14">
      <Topbar />
      <div className="mx-auto max-w-7xl space-y-5 px-6">
        <PageShell
          eyebrow="Create Project"
          title="新建项目"
          description="第一步只填写项目基础信息，不混入素材和后续阶段内容，保持输入路径清晰。"
          breadcrumbs={[
            { label: "首页", href: "/" },
            { label: "新建项目" }
          ]}
        />

        <WorkflowStepper currentStep="create" enabledSteps={["create"]} />

        <div className="animate-fade-up">
          <ProjectBasicsPrototype mode="create" />
        </div>
      </div>
    </main>
  );
}
