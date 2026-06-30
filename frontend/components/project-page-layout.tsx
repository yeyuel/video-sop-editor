import type { ReactNode } from "react";

import { PageShell, type BreadcrumbItem } from "@/components/page-shell";
import { ProjectContextBar } from "@/components/project-context-bar";
import { Topbar } from "@/components/topbar";
import { WorkflowStepper } from "@/components/workflow-stepper";
import { getWorkflowHrefMap } from "@/lib/project-nav";
import type { WorkflowStepId } from "@/lib/workflow";
import type { WorkspaceData } from "@/types/domain";
import {
  getCompletedWorkflowSteps,
  getEnabledWorkflowSteps,
  workflowSteps
} from "@/lib/workflow";

type ProjectPageLayoutProps = {
  projectId: string;
  workspace: WorkspaceData;
  currentStep: WorkflowStepId;
  eyebrow: string;
  title: string;
  description?: string;
  breadcrumbs: BreadcrumbItem[];
  aside?: ReactNode;
  topbarAction?: { label: string; href: string };
  children: ReactNode;
};

export function ProjectPageLayout({
  projectId,
  workspace,
  currentStep,
  eyebrow,
  title,
  description,
  breadcrumbs,
  aside,
  topbarAction,
  children
}: ProjectPageLayoutProps) {
  const enabledSteps = getEnabledWorkflowSteps(workspace);
  const completedSteps = getCompletedWorkflowSteps(workspace);
  const hrefMap = getWorkflowHrefMap(projectId);

  return (
    <main className="pb-14">
      <Topbar action={topbarAction} />
      <div className="mx-auto max-w-7xl space-y-5 px-6">
        <ProjectContextBar
          projectId={projectId}
          projectName={workspace.project.name}
          currentStep={currentStep}
          enabledSteps={enabledSteps}
          completedSteps={completedSteps}
          hrefMap={hrefMap}
        />

        <PageShell
          eyebrow={eyebrow}
          title={title}
          description={description}
          breadcrumbs={breadcrumbs}
          aside={
            aside ?? (
              <span className="stat-pill">
                {completedSteps.length}/{workflowSteps.length} 已完成
              </span>
            )
          }
        />

        <WorkflowStepper
          currentStep={currentStep}
          enabledSteps={enabledSteps}
          completedSteps={completedSteps}
          hrefMap={hrefMap}
        />

        <div className="animate-fade-up">{children}</div>
      </div>
    </main>
  );
}
