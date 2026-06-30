import Link from "next/link";
import clsx from "clsx";
import {
  implementedWorkflowSteps,
  workflowSteps,
  type WorkflowStepId
} from "@/lib/workflow";

type WorkflowStepperProps = {
  currentStep: WorkflowStepId;
  enabledSteps?: WorkflowStepId[];
  completedSteps?: WorkflowStepId[];
  hrefMap?: Partial<Record<WorkflowStepId, string>>;
};

function StepStatus({
  isActive,
  isCompleted,
  isEnabled
}: {
  isActive: boolean;
  isCompleted: boolean;
  isEnabled: boolean;
}) {
  if (isActive) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-white/15 px-2 py-0.5 text-[10px] font-medium">
        进行中
      </span>
    );
  }
  if (isCompleted) {
    return <span className="badge border-pine/15 bg-mist text-pine">已完成</span>;
  }
  if (isEnabled) {
    return <span className="text-[10px] font-medium text-ink/40">待处理</span>;
  }
  return <span className="text-[10px] font-medium text-ink/30">未启用</span>;
}

export function WorkflowStepper({
  currentStep,
  enabledSteps = implementedWorkflowSteps,
  completedSteps = [],
  hrefMap
}: WorkflowStepperProps) {
  return (
    <div className="surface-panel overflow-hidden p-3 md:p-4">
      <div className="mb-3 flex items-center justify-between gap-3 px-1">
        <p className="text-sm text-ink/50">制作流程</p>
        <span className="stat-pill">
          {completedSteps.length}/{workflowSteps.length}
        </span>
      </div>

      <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-6">
        {workflowSteps.map((step, index) => {
          const isActive = step.id === currentStep;
          const isEnabled = enabledSteps.includes(step.id);
          const isCompleted = completedSteps.includes(step.id);
          const href = hrefMap?.[step.id];
          const commonClassName = clsx(
            "group relative flex h-full min-h-[100px] flex-col justify-between rounded-2xl border px-4 py-3.5 transition duration-200",
            isActive &&
              "border-pine bg-pine text-white shadow-lift",
            isCompleted &&
              !isActive &&
              "border-line bg-mist/50 text-pine",
            isEnabled &&
              !isActive &&
              !isCompleted &&
              "border-line bg-white text-ink hover:-translate-y-0.5 hover:border-pine/20 hover:shadow-soft",
            !isEnabled && !isActive && "border-line bg-sand/50 text-ink/35",
            href && isEnabled && "cursor-pointer"
          );
          const content = (
            <>
              <div className="flex items-start justify-between gap-2">
                <span
                  className={clsx(
                    "inline-flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-semibold",
                    isActive
                      ? "bg-white/15 text-white"
                      : isCompleted
                        ? "bg-pine/10 text-pine"
                        : "bg-sand text-ink/45"
                  )}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <StepStatus
                  isActive={isActive}
                  isCompleted={isCompleted}
                  isEnabled={isEnabled}
                />
              </div>
              <div>
                <p className="mt-3 text-[15px] font-semibold leading-snug">{step.label}</p>
                <p
                  className={clsx(
                    "mt-1.5 text-xs leading-5",
                    isActive ? "text-white/75" : "text-ink/45"
                  )}
                >
                  {step.shortDescription}
                </p>
              </div>
            </>
          );

          return (
            <div key={step.id} className="relative min-w-0">
              {href && isEnabled ? (
                <Link href={href} className={clsx("block", commonClassName)}>
                  {content}
                </Link>
              ) : (
                <div className={commonClassName}>{content}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
