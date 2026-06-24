from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool = True
    data: Any
    meta: dict[str, str] = Field(default_factory=lambda: {"requestId": "local-dev"})


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthUserRead(BaseModel):
    id: str
    username: str
    displayName: str
    role: str
    uiEnabled: bool


class ProjectRead(BaseModel):
    id: str
    name: str
    destination: str
    platform: str
    targetDurationSec: int
    videoType: str
    stylePreference: str
    styleNotes: str
    routeText: str
    mediaRoot: str
    status: str
    selectedThemeId: str = ""


class ProjectWriteRequest(BaseModel):
    name: str
    destination: str
    platform: str
    targetDurationSec: int
    videoType: str
    stylePreference: str
    styleNotes: str = ""
    routeText: str
    mediaRoot: str
    status: str = "draft"


class ProjectCreateRequest(ProjectWriteRequest):
    pass


class ProjectUpdateRequest(ProjectWriteRequest):
    pass


class AssetRead(BaseModel):
    assetId: str
    location: str
    scene: str
    relativePath: str
    mediaType: str
    shotType: str
    emotionTags: list[str]
    visualTags: list[str]
    informationDensity: str
    suggestedDurationSec: float
    functionTags: list[str]


class AssetWriteRequest(BaseModel):
    location: str
    scene: str
    relativePath: str
    mediaType: str
    shotType: str
    emotionTags: list[str] = Field(default_factory=list)
    visualTags: list[str] = Field(default_factory=list)
    informationDensity: str
    suggestedDurationSec: float
    functionTags: list[str] = Field(default_factory=list)


class AssetCreateRequest(AssetWriteRequest):
    pass


class AssetUpdateRequest(AssetWriteRequest):
    pass


class NarrativeThemeRead(BaseModel):
    id: str
    title: str
    summary: str
    coreEmotion: str
    rhythmProfile: str
    platformReason: str
    isSelected: bool = False


class ThemeGenerateRequest(BaseModel):
    count: int = 3


class ThemeSelectRequest(BaseModel):
    themeId: str


class StoryboardSegmentRead(BaseModel):
    id: str
    startTime: float
    endTime: float
    assetId: str
    shotDescription: str
    function: str
    rhythm: str
    beatMode: str
    beatPoints: list[float]
    subtitle: str


class StoryboardSegmentWrite(BaseModel):
    id: str
    startTime: float
    endTime: float
    assetId: str
    shotDescription: str
    function: str
    rhythm: str
    beatMode: str
    beatPoints: list[float] = Field(default_factory=list)
    subtitle: str


class StoryboardGenerateRequest(BaseModel):
    themeId: str | None = None
    targetDurationSec: int | None = None
    beatMode: str | None = None
    alignToBeat: bool = True
    selectedTrackName: str | None = None


class StoryboardSaveRequest(BaseModel):
    themeId: str | None = None
    segments: list[StoryboardSegmentWrite]


class StoryboardInsertRequest(BaseModel):
    themeId: str | None = None
    afterSegmentId: str | None = None
    segment: StoryboardSegmentWrite


class StoryboardReorderRequest(BaseModel):
    orderedSegmentIds: list[str]


class StoryboardValidationRead(BaseModel):
    allSegmentsBoundToAsset: bool
    locationContinuityPassed: bool
    beatAlignmentPassed: bool
    beatAdaptationEnabled: bool
    totalDurationSec: float
    targetDurationReached: bool
    message: str = ""


class StoryboardBundleRead(BaseModel):
    segments: list[StoryboardSegmentRead]
    validation: StoryboardValidationRead


class RhythmPlanRead(BaseModel):
    bgmStyle: str
    selectedTrackName: str
    audioFileName: str = ""
    analysisSource: str = "manual"
    analysisNotes: list[str] = Field(default_factory=list)
    detectedBpm: int = 0
    audioDurationSec: float = 0.0
    rawBeatPoints: list[float] = Field(default_factory=list)
    coarseBeatPoints: list[float] = Field(default_factory=list)
    beatMode: str
    beatPoints: list[float]
    rhythmNotes: list[str]
    darkCutSuggestions: list[float]
    photoMotionSuggestions: list[str]


class RhythmPlanWriteRequest(BaseModel):
    bgmStyle: str
    selectedTrackName: str
    audioFileName: str = ""
    analysisSource: str = "manual"
    analysisNotes: list[str] = Field(default_factory=list)
    detectedBpm: int = 0
    audioDurationSec: float = 0.0
    rawBeatPoints: list[float] = Field(default_factory=list)
    coarseBeatPoints: list[float] = Field(default_factory=list)
    beatMode: str
    beatPoints: list[float] = Field(default_factory=list)
    rhythmNotes: list[str] = Field(default_factory=list)
    darkCutSuggestions: list[float] = Field(default_factory=list)
    photoMotionSuggestions: list[str] = Field(default_factory=list)


class ExportPlanRead(BaseModel):
    title: str
    shortTitle: str
    description: str
    tags: list[str]
    coverSuggestion: str


class ExportPlanWriteRequest(BaseModel):
    title: str
    shortTitle: str = ""
    description: str
    tags: list[str] = Field(default_factory=list)
    coverSuggestion: str = ""


class ExportDocumentRead(BaseModel):
    projectId: str
    format: str
    fileName: str
    content: str


class WorkspaceDataRead(BaseModel):
    project: ProjectRead
    assets: list[AssetRead]
    themes: list[NarrativeThemeRead]
    storyboard: list[StoryboardSegmentRead]
    storyboardValidation: StoryboardValidationRead
    rhythmPlan: RhythmPlanRead
    exportPlan: ExportPlanRead
