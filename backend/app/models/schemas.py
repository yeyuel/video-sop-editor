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


class AuthLoginResponse(BaseModel):
    user: AuthUserRead
    sessionToken: str
    expiresAt: str


class AuthLoginOptionRead(BaseModel):
    username: str
    displayName: str
    role: str


class LlmCallLogRead(BaseModel):
    id: str
    userId: str
    endpoint: str
    providerId: str
    model: str
    status: str
    tokenEstimate: int
    message: str
    createdAt: str


class AuthUserCreateRequest(BaseModel):
    username: str
    password: str
    displayName: str
    role: str = "editor"
    uiEnabled: bool = False


class AuthUserUpdateRequest(BaseModel):
    displayName: str | None = None
    password: str | None = None
    role: str | None = None
    uiEnabled: bool | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    destination: str
    platform: str
    targetDurationSec: int
    videoType: str
    stylePreference: str
    styleNotes: str
    routeText: str = ""
    mediaRoot: str
    status: str
    selectedThemeId: str = ""
    validateLocationOrder: bool = False


class ProjectWriteRequest(BaseModel):
    name: str
    destination: str
    platform: str
    targetDurationSec: int
    videoType: str
    stylePreference: str
    styleNotes: str = ""
    routeText: str = ""
    mediaRoot: str
    status: str = "draft"
    validateLocationOrder: bool = False


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
    usedLocations: list[str] = Field(default_factory=list)
    usedAssetIds: list[str] = Field(default_factory=list)
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
    locationOrderValidationEnabled: bool = False
    beatAlignmentPassed: bool
    beatAdaptationEnabled: bool
    totalDurationSec: float
    targetDurationSec: float = 0
    durationDeltaSec: float = 0
    durationWithinTolerance: bool = False
    targetDurationReached: bool
    unboundSegmentCount: int = 0
    issues: list[str] = Field(default_factory=list)
    message: str = ""


class ExportValidationRead(BaseModel):
    destinationMentioned: bool
    themeConsistencyPassed: bool
    message: str = ""
    issues: list[str] = Field(default_factory=list)


class StoryboardBundleRead(BaseModel):
    segments: list[StoryboardSegmentRead]
    validation: StoryboardValidationRead


class BgmRecommendationRead(BaseModel):
    id: str
    title: str
    artist: str = ""
    styleTags: list[str] = Field(default_factory=list)
    mood: str = ""
    bpmRange: str = ""
    fitReason: str = ""
    searchHint: str = ""
    platformTips: str = ""
    isSelected: bool = False


class BgmSelectionRequest(BaseModel):
    recommendationId: str


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
    recommendedBgm: list[BgmRecommendationRead] = Field(default_factory=list)
    selectedBgmId: str = ""
    bgmPhase: str = "empty"


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
    recommendedBgm: list[BgmRecommendationRead] | None = None
    selectedBgmId: str | None = None
    bgmPhase: str | None = None


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
    exportValidation: ExportValidationRead
    rhythmPlan: RhythmPlanRead
    exportPlan: ExportPlanRead


class LlmProviderRead(BaseModel):
    providerId: str
    providerName: str
    authTypes: list[str]
    defaultBaseUrl: str
    defaultModel: str
    openaiCompatible: bool = True
    status: str
    isActive: bool = False
    models: list["LlmModelOptionRead"] = Field(default_factory=list)


class LlmModelOptionRead(BaseModel):
    modelId: str
    label: str
    description: str = ""
    recommended: bool = False


class LlmProviderConfigWriteRequest(BaseModel):
    authType: str = "api_key"
    baseUrl: str = ""
    model: str = ""
    apiKey: str = ""


class LlmStatusRead(BaseModel):
    providerId: str
    providerName: str
    authType: str
    status: str
    baseUrl: str
    model: str
    configured: bool
    message: str = ""


class LlmOAuthStartRead(BaseModel):
    authorizationUrl: str = ""
    state: str = ""
    message: str = ""


class LlmDeviceCodeStartRead(BaseModel):
    deviceCode: str = ""
    userCode: str = ""
    verificationUri: str = ""
    expiresIn: int = 0
    interval: int = 0
    message: str = ""


class LlmProviderTestRead(BaseModel):
    ok: bool
    providerId: str
    providerName: str
    model: str
    baseUrl: str
    endpointUrl: str
    latencyMs: int = 0
    llmStatus: str
    message: str
    replyPreview: str = ""
