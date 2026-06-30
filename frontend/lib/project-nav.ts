import type { WorkflowStepId } from "@/lib/workflow";

export function getWorkflowHrefMap(projectId: string): Record<WorkflowStepId, string> {
  return {
    create: `/projects/${projectId}`,
    assets: `/projects/${projectId}/assets`,
    theme: `/projects/${projectId}/themes`,
    rhythm: `/projects/${projectId}/rhythm`,
    storyboard: `/projects/${projectId}/storyboard`,
    export: `/projects/${projectId}/export`
  };
}

export function projectBreadcrumbs(
  projectId: string,
  projectName: string,
  currentLabel: string
) {
  return [
    { label: "首页", href: "/" },
    { label: projectName, href: `/projects/${projectId}` },
    { label: currentLabel }
  ];
}

export function storyboardSubBreadcrumbs(
  projectId: string,
  projectName: string,
  subLabel: string
) {
  return [
    { label: "首页", href: "/" },
    { label: projectName, href: `/projects/${projectId}` },
    { label: "分镜", href: `/projects/${projectId}/storyboard` },
    { label: subLabel }
  ];
}
