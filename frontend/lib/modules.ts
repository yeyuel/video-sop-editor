export type WorkspaceModule = {
  id: string;
  label: string;
  title: string;
  description: string;
};

export const workspaceModules: WorkspaceModule[] = [
  {
    id: "project-setup",
    label: "项目创建",
    title: "项目创建",
    description: "维护项目基础信息、平台、目标时长、风格偏好和路线。"
  },
  {
    id: "asset-intake",
    label: "素材录入",
    title: "素材录入",
    description: "查看结构化素材卡片，后续可扩展为上传、标签编辑和脑图录入。"
  },
  {
    id: "theme-generation",
    label: "主题生成",
    title: "主题生成",
    description: "从素材出发选择叙事方向，驱动后续节奏和分镜生成。"
  },
  {
    id: "rhythm-planning",
    label: "节奏规划",
    title: "节奏规划",
    description: "管理 BGM、节拍模式、卡点和镜头节奏说明。"
  },
  {
    id: "storyboard-generation",
    label: "分镜生成",
    title: "分镜生成",
    description: "输出逐秒时间线、素材引用和 beat points。"
  },
  {
    id: "export-plan",
    label: "导出",
    title: "导出",
    description: "整理标题、文案、标签和多格式导出内容。"
  }
];
