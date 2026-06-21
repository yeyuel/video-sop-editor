import type { WorkspaceData } from "@/types/domain";

export type WorkflowStepId =
  | "create"
  | "assets"
  | "theme"
  | "rhythm"
  | "storyboard"
  | "export";

export type WorkflowStep = {
  id: WorkflowStepId;
  label: string;
  shortDescription: string;
};

export const workflowSteps: WorkflowStep[] = [
  {
    id: "create",
    label: "新建",
    shortDescription: "填写项目基本信息"
  },
  {
    id: "assets",
    label: "录入",
    shortDescription: "录入并整理素材"
  },
  {
    id: "theme",
    label: "主题",
    shortDescription: "选择叙事方向"
  },
  {
    id: "rhythm",
    label: "节奏",
    shortDescription: "规划节拍和卡点"
  },
  {
    id: "storyboard",
    label: "分镜",
    shortDescription: "生成时间线脚本"
  },
  {
    id: "export",
    label: "导出",
    shortDescription: "整理标题标签文案"
  }
];

export const implementedWorkflowSteps: WorkflowStepId[] = workflowSteps.map((step) => step.id);

export function getEnabledWorkflowSteps(workspace: WorkspaceData): WorkflowStepId[] {
  const enabled: WorkflowStepId[] = ["create"];

  if (workspace.project.id) {
    enabled.push("assets");
  }
  if (workspace.assets.length > 0) {
    enabled.push("theme");
  }
  if (workspace.themes.length > 0 && workspace.project.selectedThemeId) {
    enabled.push("rhythm");
    enabled.push("storyboard");
  }
  if (workspace.storyboard.length > 0) {
    enabled.push("export");
  }

  return enabled;
}

export function getCompletedWorkflowSteps(workspace: WorkspaceData): WorkflowStepId[] {
  const completed: WorkflowStepId[] = [];

  if (workspace.project.name) {
    completed.push("create");
  }
  if (workspace.assets.length > 0) {
    completed.push("assets");
  }
  if (workspace.project.selectedThemeId) {
    completed.push("theme");
  }
  if (workspace.rhythmPlan.beatPoints.length > 0) {
    completed.push("rhythm");
  }
  if (workspace.storyboard.length > 0) {
    completed.push("storyboard");
  }
  if (workspace.exportPlan.title && workspace.exportPlan.description) {
    completed.push("export");
  }

  return completed;
}

export function getProjectStage(workspace: WorkspaceData): WorkflowStepId {
  const completed = getCompletedWorkflowSteps(workspace);
  const nextStep = workflowSteps.find((step) => !completed.includes(step.id));
  return nextStep?.id ?? "export";
}
