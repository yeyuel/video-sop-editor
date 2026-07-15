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
  { value: "beat_1", label: "踩节拍（粗密度）" },
  { value: "beat_2", label: "踩节拍（细密度）" },
  { value: "strong_weak", label: "强弱拍（强拍）" }
];

export const storyboardAttentionRoleOptions = [
  { value: "", label: "不设置" },
  { value: "hook", label: "开头钩子" },
  { value: "setup", label: "叙事铺垫" },
  { value: "develop_1", label: "第一次展开" },
  { value: "develop_2", label: "第二次展开" },
  { value: "climax_build", label: "高潮铺垫" },
  { value: "turn_1", label: "第一次反转" },
  { value: "turn_2", label: "第二次反转" },
  { value: "push", label: "推进" },
  { value: "climax", label: "高潮" },
  { value: "payoff", label: "记忆点回收" },
  { value: "visual_seed", label: "视觉种草" },
  { value: "info_value", label: "信息价值" },
  { value: "experience", label: "体验展开" },
  { value: "decision_push", label: "决策推动" },
  { value: "save_cta", label: "收藏提示" },
  { value: "chapter", label: "章节节点" },
  { value: "chapter_setup", label: "章节铺垫" },
  { value: "chapter_bridge", label: "章节过渡" },
  { value: "proof", label: "信息证明" },
  { value: "detail", label: "细节补充" },
  { value: "summary", label: "总结回收" },
  { value: "immersion", label: "沉浸铺陈" },
  { value: "inner_turn", label: "情绪转折" },
  { value: "emotion_build", label: "情绪递进" },
  { value: "emotional_climax", label: "情绪高潮" },
  { value: "afterglow", label: "余韵过渡" },
  { value: "aftertaste", label: "留白回味" },
  { value: "buffer", label: "缓冲" },
  { value: "ending", label: "收尾" },
  { value: "supporting", label: "辅助" }
];

export const storyboardVisualStrengthOptions = [
  { value: "", label: "不设置" },
  { value: "strong", label: "强视觉" },
  { value: "medium", label: "中等视觉" },
  { value: "weak", label: "弱视觉" }
];

export const storyboardMotionPolicyOptions = [
  { value: "", label: "不设置" },
  { value: "hold_or_speed_ramp", label: "停留或变速" },
  { value: "slow_push", label: "照片慢推" },
  { value: "gentle_zoom", label: "轻微缩放" },
  { value: "natural_cut", label: "自然切换" }
];

export const storyboardTransitionPolicyOptions = [
  { value: "", label: "不设置" },
  { value: "hard_cut", label: "硬切" },
  { value: "clean_cut", label: "干净切" },
  { value: "fade_or_match_cut", label: "淡入淡出/匹配切" }
];

export const storyboardSubtitlePolicyOptions = [
  { value: "", label: "自动（按叙事角色）" },
  { value: "standard", label: "常规字幕" },
  { value: "emphasis", label: "重点字幕" },
  { value: "info", label: "信息字幕" },
  { value: "minimal", label: "弱化字幕" }
];

export const storyboardVoiceoverRoleOptions = [
  { value: "", label: "不设置" },
  { value: "narration", label: "旁白叙述" },
  { value: "guide", label: "攻略讲解" },
  { value: "emotion", label: "情绪独白" },
  { value: "transition", label: "转场串联" },
  { value: "cta", label: "互动引导" }
];

export const storyboardVoiceoverTimingOptions = [
  { value: "", label: "不设置" },
  { value: "follow_segment", label: "跟随当前镜头" },
  { value: "lead_in", label: "提前进入" },
  { value: "tail_out", label: "延后收束" },
  { value: "span_next", label: "跨到下一镜头" }
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

export function getStoryboardAttentionRoleLabel(value: string) {
  return (
    storyboardAttentionRoleOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}

export function getStoryboardVisualStrengthLabel(value: string) {
  return (
    storyboardVisualStrengthOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}

export function getStoryboardMotionPolicyLabel(value: string) {
  return (
    storyboardMotionPolicyOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}

export function getStoryboardTransitionPolicyLabel(value: string) {
  return (
    storyboardTransitionPolicyOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}

export function getStoryboardSubtitlePolicyLabel(value: string) {
  return (
    storyboardSubtitlePolicyOptions.find((option) => option.value === value)?.label ?? value
  ) || "自动（按叙事角色）";
}

export function getStoryboardVoiceoverRoleLabel(value: string) {
  return (
    storyboardVoiceoverRoleOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}

export function getStoryboardVoiceoverTimingLabel(value: string) {
  return (
    storyboardVoiceoverTimingOptions.find((option) => option.value === value)?.label ?? value
  ) || "不设置";
}
