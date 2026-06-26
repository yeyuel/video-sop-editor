export type LlmStageDefinition = {
  id: string;
  label: string;
};

export const THEME_LLM_STAGES: LlmStageDefinition[] = [
  { id: "preparing", label: "读取项目与素材" },
  { id: "configuring", label: "加载模型配置" },
  { id: "calling_llm", label: "模型生成主题" },
  { id: "parsing", label: "解析模型输出" },
  { id: "building", label: "整理候选主题" },
  { id: "fallback", label: "规则回退（如需要）" },
  { id: "saving", label: "保存到项目" }
];

export const STORYBOARD_LLM_STAGES: LlmStageDefinition[] = [
  { id: "preparing", label: "读取主题与素材" },
  { id: "configuring", label: "加载模型配置" },
  { id: "calling_llm", label: "模型生成分镜" },
  { id: "parsing", label: "解析模型输出" },
  { id: "building", label: "组装时间线" },
  { id: "fallback", label: "规则回退（如需要）" },
  { id: "saving", label: "保存分镜" }
];

export const BGM_RECOMMEND_LLM_STAGES: LlmStageDefinition[] = [
  { id: "preparing", label: "读取项目与主题" },
  { id: "configuring", label: "加载模型配置" },
  { id: "calling_llm", label: "模型推荐 BGM" },
  { id: "parsing", label: "解析推荐结果" },
  { id: "building", label: "整理候选曲目" },
  { id: "fallback", label: "规则回退（如需要）" },
  { id: "saving", label: "保存推荐" }
];

export const RHYTHM_LLM_STAGES: LlmStageDefinition[] = [
  { id: "preparing", label: "读取项目与主题" },
  { id: "analyzing_audio", label: "分析音频节拍" },
  { id: "building_beats", label: "生成节拍点" },
  { id: "configuring", label: "加载模型配置" },
  { id: "calling_llm", label: "模型生成节奏文案" },
  { id: "parsing", label: "解析模型输出" },
  { id: "building", label: "整理节奏规划" },
  { id: "fallback", label: "规则回退（如需要）" },
  { id: "saving", label: "保存节奏规划" }
];

export const EXPORT_LLM_STAGES: LlmStageDefinition[] = [
  { id: "preparing", label: "读取项目与分镜" },
  { id: "configuring", label: "加载模型配置" },
  { id: "calling_llm", label: "模型生成发布文案" },
  { id: "parsing", label: "解析模型输出" },
  { id: "building", label: "整理导出字段" },
  { id: "fallback", label: "规则回退（如需要）" },
  { id: "saving", label: "保存导出信息" }
];

export const LLM_TEST_STAGES: LlmStageDefinition[] = [
  { id: "configuring", label: "加载模型配置" },
  { id: "calling_llm", label: "测试模型连通性" },
  { id: "parsing", label: "解析测试结果" }
];

export type LlmProgressViewState = {
  title: string;
  stages: LlmStageDefinition[];
  currentStage: string;
  message: string;
  detail: string;
  progress: number;
  startedAt: number;
};

export function createLlmProgressState(
  title: string,
  stages: LlmStageDefinition[]
): LlmProgressViewState {
  return {
    title,
    stages,
    currentStage: stages[0]?.id ?? "preparing",
    message: "正在启动…",
    detail: "首次生成通常需要 30–90 秒",
    progress: 0,
    startedAt: Date.now()
  };
}

export function applyLlmProgressEvent(
  state: LlmProgressViewState,
  event: {
    stage?: string;
    message?: string;
    detail?: string;
    progress?: number;
  }
): LlmProgressViewState {
  return {
    ...state,
    currentStage: event.stage ?? state.currentStage,
    message: event.message ?? state.message,
    detail: event.detail ?? state.detail,
    progress: event.progress ?? state.progress
  };
}

export function stageStatus(
  stages: LlmStageDefinition[],
  stageId: string,
  currentStage: string
): "done" | "active" | "pending" {
  const order = stages.map((item) => item.id);
  const currentIndex = order.indexOf(currentStage);
  const stageIndex = order.indexOf(stageId);
  if (stageIndex === -1) {
    return "pending";
  }
  if (stageId === currentStage) {
    return "active";
  }
  if (currentIndex === -1) {
    return "pending";
  }
  return stageIndex < currentIndex ? "done" : "pending";
}

export function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins <= 0) {
    return `${secs}s`;
  }
  return `${mins}m ${secs.toString().padStart(2, "0")}s`;
}
