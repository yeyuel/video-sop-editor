export const storyboardFunctionOptions = [
  { value: "", label: "不设置" },
  { value: "opening_hook", label: "开头钩子" },
  { value: "rhythm_hit", label: "节奏刺点" },
  { value: "main_climax", label: "主高潮" },
  { value: "slow_climax", label: "慢高潮" },
  { value: "transition_buffer", label: "过渡缓冲" },
  { value: "supporting", label: "辅助镜头" },
  { value: "ending", label: "结尾收束" }
];

export const storyboardBeatModeOptions = [
  { value: "none", label: "不启用节拍" },
  { value: "beat_1", label: "踩节拍1（粗密度）" },
  { value: "beat_2", label: "踩节拍2（细密度）" },
  { value: "strong_weak", label: "强弱拍（强拍）" }
];

export function getStoryboardFunctionLabel(value: string) {
  return (
    storyboardFunctionOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}

export function getStoryboardBeatModeLabel(value: string) {
  return (
    storyboardBeatModeOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}
