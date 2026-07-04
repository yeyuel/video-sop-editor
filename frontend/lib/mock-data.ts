import type {
  ExportPlan,
  Project,
  StoryboardValidation,
  WorkspaceData
} from "@/types/domain";

export const fallbackProjects: Project[] = [
  {
    id: "proj_001",
    name: "五月的台州",
    destination: "台州",
    platform: "douyin",
    targetDurationSec: 40,
    videoType: "travel_montage",
    stylePreference: "旅行攻略片",
    styleNotes: "绿色调，无旁边，空境为主",
    routeText: "国清寺-天台山-神仙居",
    mediaRoot: "E:\\自媒体\\2025-台州-p3",
    status: "draft",
    selectedThemeId: "theme_5ddee337",
    validateLocationOrder: false,
    allowAssetReuse: false
  }
];

const fallbackValidation: StoryboardValidation = {
  allSegmentsBoundToAsset: true,
  locationContinuityPassed: true,
  locationOrderValidationEnabled: false,
  beatAlignmentPassed: true,
  beatAdaptationEnabled: true,
  totalDurationSec: 2.5,
  targetDurationSec: 60,
  durationDeltaSec: -57.5,
  durationWithinTolerance: false,
  targetDurationReached: false,
  unboundSegmentCount: 0,
  assetReuseEnabled: false,
  reusedAssetCount: 0,
  reusedSegmentCount: 0,
  issues: ["总时长 2.5s 低于目标 60s（差 57.5s）"],
  message: "总时长 2.5s 低于目标 60s（差 57.5s）"
};

const fallbackExportValidation = {
  destinationMentioned: true,
  themeConsistencyPassed: true,
  message: "导出文案与项目目的地、主题一致。",
  issues: [] as string[]
};

const fallbackExportPlan: ExportPlan = {
  title: "五月台州绿到失语",
  shortTitle: "台州绿意路线",
  description:
    "五月去台州，这条线真的很治愈。\n国清寺先静下来，天台山看飞瀑，神仙居走进云雾里。\n路线：国清寺-天台山-神仙居。\n喜欢这种清幽空镜旅行吗？",
  tags: ["台州旅行", "五月出游", "治愈系风景", "旅行攻略"],
  coverSuggestion:
    "选国清寺石牌坊或神仙居云雾红桥作封面，主体居中；封面字用“五月台州绿到失语”，白字加深绿描边，突出清幽绿色调，避免遮挡牌坊和桥体。"
};

export const fallbackWorkspace: WorkspaceData = {
  project: fallbackProjects[0],
  assets: [
    {
      assetId: "OUTPUT_001",
      location: "国清寺",
      scene: "仰拍寺庙橙色墙体与灰瓦屋檐，树冠遮蔽天空，前景有树干和石狮剪影，远处可见青山与少量游客。",
      relativePath: "output/国清寺寺门.mp4",
      mediaType: "video",
      shotType: "wide",
      emotionTags: ["静谧", "古朴", "庄严", "清幽"],
      visualTags: ["寺庙建筑", "灰瓦屋檐", "树冠", "石狮剪影", "橙色墙面", "山林背景"],
      informationDensity: "medium",
      suggestedDurationSec: 2,
      functionTags: ["transition_buffer"]
    },
    {
      assetId: "国清寺_006",
      location: "国清寺",
      scene: "仰拍古典石牌坊与龙纹雕刻，镜头掠过浓密绿荫，末尾可见游客在林下步道穿行。",
      relativePath: "output/国清寺进门.mp4",
      mediaType: "video",
      shotType: "wide",
      emotionTags: ["清幽", "古朴", "宁静", "游览感"],
      visualTags: ["石牌坊", "龙纹雕刻", "绿树成荫", "仰拍视角", "游客", "园林"],
      informationDensity: "medium",
      suggestedDurationSec: 2,
      functionTags: ["opening_hook"]
    }
  ],
  themes: [
    {
      id: "theme_5ddee337",
      title: "绿意禅行：从国清寺走进五月台州",
      summary:
        "以国清寺的石牌坊、橙墙灰瓦、香炉烟雾和林下参道作为开篇，突出“先安静下来，再出发”的旅行攻略感。",
      coreEmotion: "清幽",
      rhythmProfile: "前3秒用国清寺_006仰拍牌坊做钩子；中段以寺墙屋檐作慢节奏铺陈。",
      platformReason: "抖音旅行攻略片需要快速建立目的地识别，国清寺牌坊和橙墙辨识度强。",
      usedLocations: ["国清寺", "output"],
      usedAssetIds: ["国清寺_006", "OUTPUT_001"],
      isSelected: true
    }
  ],
  storyboard: [
    {
      id: "seg_ffcb30a1",
      startTime: 0,
      endTime: 0.9,
      assetId: "国清寺_006",
      shotDescription: "强拍切入，仰拍石牌坊与龙纹雕刻，开场先定下清幽古意。",
      function: "opening_hook",
      rhythm: "balanced",
      beatMode: "strong_weak",
      beatPoints: [0, 0.9],
      subtitle: "五月台州，先在国清寺安静下来",
      attentionRole: "hook",
      visualStrength: "strong",
      motionPolicy: "hold_or_speed_ramp",
      transitionPolicy: "hard_cut"
    },
    {
      id: "seg_0f0e0b0d",
      startTime: 0.9,
      endTime: 3.85,
      assetId: "OUTPUT_001",
      shotDescription: "寺墙屋檐慢铺，绿色树冠与橙墙形成对比。",
      function: "transition_buffer",
      rhythm: "balanced",
      beatMode: "strong_weak",
      beatPoints: [0.9, 3.85],
      subtitle: "橙墙灰瓦，五月绿到失语",
      attentionRole: "buffer",
      visualStrength: "medium",
      motionPolicy: "natural_cut",
      transitionPolicy: "fade_or_match_cut"
    }
  ],
  storyboardValidation: fallbackValidation,
  exportValidation: fallbackExportValidation,
  rhythmPlan: {
    bgmStyle: "57BPM舒展禅意氛围慢脉冲，木质打击轻点配柔和环境铺底",
    selectedTrackName: "風の住む街",
    audioFileName: "風の住む街.mp3",
    analysisSource: "audio_upload",
    analysisNotes: ["识别 BPM：57"],
    detectedBpm: 57,
    audioDurationSec: 44.86,
    rawBeatPoints: [],
    coarseBeatPoints: [],
    beatMode: "strong_weak",
    beatPoints: [0, 0.9, 3.85, 7.5, 11.35, 14.1, 27.45, 33.7, 36.55, 40],
    rhythmNotes: ["前3秒用国清寺_006卡第1个强拍切入，牌坊仰拍做安静钩子"],
    darkCutSuggestions: [10.1, 20.1, 29.9],
    photoMotionSuggestions: ["当前以视频素材为主，可在情绪段落加入轻微速度变化。"],
    recommendedBgm: [],
    selectedBgmId: "bgm_e8dccff1",
    bgmPhase: "analyzed",
    rhythmProfile: {
      mode: "highlight_reel",
      cutDensity: "fast",
      subtitleDensity: "strong_hook",
      motionPolicy: "快切为主，照片只用于强视觉定格或轻微推拉。",
      attentionIntervalSec: 12
    },
    attentionBeats: [
      { time: 0, role: "hook", label: "开头钩子" },
      { time: 10, role: "push", label: "推进" },
      { time: 20, role: "turn", label: "反转" },
      { time: 30, role: "climax", label: "高潮" },
      { time: 40, role: "ending", label: "收尾" }
    ],
    beatCalibration: {
      source: "audio_upload",
      beatOffsetSec: 0,
      densityMode: "strong_weak",
      referenceBeatPoints: []
    },
    audioFingerprint: "風の住む街.mp3:44.86:57",
    audioAnalysisVersion: "mock"
  },
  exportPlan: fallbackExportPlan
};
