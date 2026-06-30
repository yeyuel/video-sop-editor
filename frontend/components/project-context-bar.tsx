import Link from "next/link";
import clsx from "clsx";

import { workflowSteps, type WorkflowStepId } from "@/lib/workflow";

type ProjectContextBarProps = {
  projectId: string;
  projectName: string;
  currentStep: WorkflowStepId;
  enabledSteps: WorkflowStepId[];
  completedSteps: WorkflowStepId[];
  hrefMap: Record<WorkflowStepId, string>;
};

export function ProjectContextBar({
  projectId,
  projectName,
  currentStep,
  enabledSteps,
  completedSteps,
  hrefMap
}: ProjectContextBarProps) {
  return (
    <div className="surface-panel px-4 py-3">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-[0.24em] text-ink/40">
            当前项目
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <Link
              href={`/projects/${projectId}`}
              className="truncate text-base font-semibold text-ink transition hover:text-pine"
            >
              {projectName}
            </Link>
            <span className="stat-pill">
              {completedSteps.length}/{workflowSteps.length} 阶段完成
            </span>
          </div>
        </div>

        <nav
          aria-label="项目工作流快捷导航"
          className="flex flex-wrap gap-1.5"
        >
          {workflowSteps.map((step) => {
            const isActive = step.id === currentStep;
            const isEnabled = enabledSteps.includes(step.id);
            const isCompleted = completedSteps.includes(step.id);
            const href = hrefMap[step.id];

            const className = clsx(
              "rounded-full px-3 py-1.5 text-xs font-medium transition",
              isActive && "bg-pine text-white shadow-sm",
              !isActive && isCompleted && "bg-mist text-pine",
              !isActive && isEnabled && !isCompleted && "bg-sand text-ink/65 hover:bg-white hover:text-pine",
              !isEnabled && !isActive && "cursor-not-allowed bg-sand/60 text-ink/30"
            );

            if (href && isEnabled && !isActive) {
              return (
                <Link key={step.id} href={href} className={className}>
                  {step.label}
                </Link>
              );
            }

            return (
              <span key={step.id} className={className} aria-current={isActive ? "page" : undefined}>
                {step.label}
              </span>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
