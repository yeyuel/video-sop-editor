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
  beatAlignmentPassed: boolean;
  totalDurationSec: number;
};

export type StoryboardBundle = {
  segments: StoryboardSegment[];
  validation: StoryboardValidation;
};

export type RhythmPlan = {
  bgmStyle: string;
  selectedTrackName: string;
  beatMode: string;
  beatPoints: number[];
  rhythmNotes: string[];
  darkCutSuggestions: number[];
  photoMotionSuggestions: string[];
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

export type WorkspaceData = {
  project: Project;
  assets: Asset[];
  themes: NarrativeTheme[];
  storyboard: StoryboardSegment[];
  storyboardValidation: StoryboardValidation;
  rhythmPlan: RhythmPlan;
  exportPlan: ExportPlan;
};
