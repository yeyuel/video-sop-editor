import type {
  ExportPlan,
  Project,
  StoryboardValidation,
  WorkspaceData
} from "@/types/domain";

export const fallbackProjects: Project[] = [
  {
    id: "proj_001",
    name: "阿勒泰雪国片",
    destination: "阿勒泰",
    platform: "xiaohongshu",
    targetDurationSec: 60,
    videoType: "emotion_film",
    stylePreference: "情绪氛围片",
    styleNotes: "冷蓝色调，空镜为主，结尾保留回味感。",
    routeText: "将军山 - 喀纳斯 - 禾木",
    mediaRoot: "D:\\素材库\\阿勒泰项目",
    status: "draft",
    selectedThemeId: "theme_001"
  }
];

const fallbackValidation: StoryboardValidation = {
  allSegmentsBoundToAsset: true,
  locationContinuityPassed: true,
  beatAlignmentPassed: true,
  beatAdaptationEnabled: true,
  totalDurationSec: 2.5,
  targetDurationReached: false,
  message: "素材已全部使用完，当前总时长未达到目标时长。建议补充素材，或先将长素材切分后分别录入。"
};

const fallbackExportPlan: ExportPlan = {
  title: "原来冬天的阿勒泰，真的像童话",
  shortTitle: "阿勒泰雪国童话",
  description: "把雪、木屋和路上的人，剪成一段安静但有记忆点的冬日旅程。",
  tags: ["阿勒泰", "旅行剪辑", "冬日雪景"],
  coverSuggestion: "优先使用禾木木屋群远景，标题放在右下角保留雪景留白。"
};

export const fallbackWorkspace: WorkspaceData = {
  project: fallbackProjects[0],
  assets: [
    {
      assetId: "KANAS_001",
      location: "喀纳斯",
      scene: "蓝冰河流特写，前景带雪面纹理",
      relativePath: "喀纳斯/drone/KANAS_001.mp4",
      mediaType: "drone_video",
      shotType: "subject_medium",
      emotionTags: ["冷", "静"],
      visualTags: ["冷蓝", "白雪"],
      informationDensity: "medium",
      suggestedDurationSec: 1.5,
      functionTags: ["slow_climax"]
    },
    {
      assetId: "HEMU_002",
      location: "禾木",
      scene: "木屋群远景，晨雾从屋顶掠过",
      relativePath: "禾木/wide/HEMU_002.mp4",
      mediaType: "video",
      shotType: "wide",
      emotionTags: ["童话"],
      visualTags: ["蓝调", "木屋"],
      informationDensity: "high",
      suggestedDurationSec: 1,
      functionTags: ["opening_hook"]
    }
  ],
  themes: [
    {
      id: "theme_001",
      title: "阿勒泰情绪氛围片",
      summary: "用雪国空镜和人物经过的瞬间，做一支带沉浸感的冬日旅行短片。",
      coreEmotion: "沉浸",
      rhythmProfile: "前段抓人，中段放缓，结尾回味",
      platformReason: "适合小红书做氛围种草，也方便后续扩展成口播版。",
      isSelected: true
    }
  ],
  storyboard: [
    {
      id: "seg_001",
      startTime: 0,
      endTime: 1,
      assetId: "HEMU_002",
      shotDescription: "禾木木屋群远景作为开头钩子",
      function: "opening_hook",
      rhythm: "tight_cut",
      beatMode: "beat_1",
      beatPoints: [0, 0.5, 1],
      subtitle: "像一脚走进了雪国童话"
    },
    {
      id: "seg_002",
      startTime: 1,
      endTime: 2.5,
      assetId: "KANAS_001",
      shotDescription: "喀纳斯蓝冰河流特写承接中段情绪",
      function: "slow_climax",
      rhythm: "balanced",
      beatMode: "beat_1",
      beatPoints: [1, 1.5, 2, 2.5],
      subtitle: "冷蓝色的河面，把情绪慢慢拉开"
    }
  ],
  storyboardValidation: fallbackValidation,
  rhythmPlan: {
    bgmStyle: "冷感氛围电子 + 轻鼓点",
    selectedTrackName: "snow-dream-demo",
    audioFileName: "",
    analysisSource: "rule",
    analysisNotes: ["当前为规则生成节拍点，尚未上传真实音频。"],
    detectedBpm: 0,
    audioDurationSec: 0,
    rawBeatPoints: [],
    beatMode: "beat_1",
    beatPoints: [0, 0.5, 1, 1.5, 2, 2.5],
    rhythmNotes: [
      "前 3 秒保证强开头，优先用高识别度空镜。",
      "中段适当放慢切换频率，把雪国的安静感留出来。",
      "高潮段回到最有动势的素材，形成记忆点。"
    ],
    darkCutSuggestions: [15, 30, 45],
    photoMotionSuggestions: ["照片素材可用轻推或停留 1-2 拍，避免和视频一起快切。"]
  },
  exportPlan: fallbackExportPlan
};
