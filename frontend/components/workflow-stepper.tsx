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

export function WorkflowStepper({
  currentStep,
  enabledSteps = implementedWorkflowSteps,
  completedSteps = [],
  hrefMap
}: WorkflowStepperProps) {
  return (
    <div className="rounded-xl2 border border-black/5 bg-white/90 p-4 shadow-card backdrop-blur">
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-6">
        {workflowSteps.map((step, index) => {
          const isActive = step.id === currentStep;
          const isEnabled = enabledSteps.includes(step.id);
          const isCompleted = completedSteps.includes(step.id);
          const href = hrefMap?.[step.id];
          const commonClassName = clsx(
            "flex h-full min-h-[116px] flex-col justify-between rounded-2xl border px-5 py-3 transition",
            isActive && "border-pine bg-pine text-white",
            isCompleted && !isActive && "border-pine/15 bg-mist text-pine",
            isEnabled && !isActive && !isCompleted && "border-black/5 bg-sand/70 text-ink",
            !isEnabled && !isActive && "border-black/5 bg-white text-ink/45",
            href && isEnabled && "hover:-translate-y-0.5"
          );
          const content = (
            <>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-[0.2em]">0{index + 1}</p>
                <span
                  className={clsx(
                    "text-xs font-medium",
                    isActive ? "text-white/80" : "text-pine/60"
                  )}
                >
                  {isCompleted ? "已完成" : isActive ? "进行中" : "待处理"}
                </span>
              </div>
              <p className="mt-2 text-base font-semibold">{step.label}</p>
              <p className="mt-1 text-xs leading-5 opacity-80">{step.shortDescription}</p>
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
              {index < workflowSteps.length - 1 ? (
                <div className="pointer-events-none absolute -right-5 top-1/2 hidden w-5 -translate-y-1/2 xl:flex items-center justify-center">
                  <span className="text-xl leading-none text-pine/25">→</span>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
