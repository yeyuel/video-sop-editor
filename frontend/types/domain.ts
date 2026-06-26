export type Project = {
  id: string;
  name: string;
  destination: string;
  platform: string;
  targetDurationSec: number;
  videoType: string;
  stylePreference: string;
  styleNotes: string;
  routeText: string;
  mediaRoot: string;
  status: string;
  selectedThemeId: string;
  validateLocationOrder: boolean;
};

export type Asset = {
  assetId: string;
  location: string;
  scene: string;
  relativePath: string;
  mediaType: string;
  shotType: string;
  emotionTags: string[];
  visualTags: string[];
  informationDensity: string;
  suggestedDurationSec: number;
  functionTags: string[];
};

export type NarrativeTheme = {
  id: string;
  title: string;
  summary: string;
  coreEmotion: string;
  rhythmProfile: string;
  platformReason: string;
  usedLocations: string[];
  usedAssetIds: string[];
  isSelected: boolean;
};

export type StoryboardSegment = {
  id: string;
  startTime: number;
  endTime: number;
  assetId: string;
  shotDescription: string;
  function: string;
  rhythm: string;
  beatMode: string;
  beatPoints: number[];
  subtitle: string;
};

export type StoryboardValidation = {
  allSegmentsBoundToAsset: boolean;
  locationContinuityPassed: boolean;
  locationOrderValidationEnabled: boolean;
  beatAlignmentPassed: boolean;
  beatAdaptationEnabled: boolean;
  totalDurationSec: number;
  targetDurationSec: number;
  durationDeltaSec: number;
  durationWithinTolerance: boolean;
  targetDurationReached: boolean;
  unboundSegmentCount: number;
  issues: string[];
  message: string;
};

export type ExportValidation = {
  destinationMentioned: boolean;
  themeConsistencyPassed: boolean;
  message: string;
  issues: string[];
};

export type StoryboardBundle = {
  segments: StoryboardSegment[];
  validation: StoryboardValidation;
};

export type BgmRecommendation = {
  id: string;
  title: string;
  artist: string;
  styleTags: string[];
  mood: string;
  bpmRange: string;
  fitReason: string;
  searchHint: string;
  platformTips: string;
  isSelected: boolean;
};

export type RhythmPlan = {
  bgmStyle: string;
  selectedTrackName: string;
  audioFileName: string;
  analysisSource: string;
  analysisNotes: string[];
  detectedBpm: number;
  audioDurationSec: number;
  rawBeatPoints: number[];
  coarseBeatPoints: number[];
  beatMode: string;
  beatPoints: number[];
  rhythmNotes: string[];
  darkCutSuggestions: number[];
  photoMotionSuggestions: string[];
  recommendedBgm: BgmRecommendation[];
  selectedBgmId: string;
  bgmPhase: "empty" | "recommended" | "analyzed";
};

export type ExportPlan = {
  title: string;
  shortTitle: string;
  description: string;
  tags: string[];
  coverSuggestion: string;
};

export type ExportDocument = {
  projectId: string;
  format: string;
  fileName: string;
  content: string;
};

export type AuthUser = {
  id: string;
  username: string;
  displayName: string;
  role: string;
  uiEnabled: boolean;
};

export type WorkspaceData = {
  project: Project;
  assets: Asset[];
  themes: NarrativeTheme[];
  storyboard: StoryboardSegment[];
  storyboardValidation: StoryboardValidation;
  exportValidation: ExportValidation;
  rhythmPlan: RhythmPlan;
  exportPlan: ExportPlan;
};
