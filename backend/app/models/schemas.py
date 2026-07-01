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
    jianyingDraftRoot: str = ""
    status: str
    selectedThemeId: str = ""
    validateLocationOrder: bool = False
    allowAssetReuse: bool = False


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
    jianyingDraftRoot: str = ""
    status: str = "draft"
    validateLocationOrder: bool = False
    allowAssetReuse: bool = False


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
    visionAnalysisStatus: str = "empty"
    visionPrefilledFields: list[str] = Field(default_factory=list)
    visionAnalysisMessage: str = ""


class AssetVisionPrefillRead(BaseModel):
    scene: str = ""
    shotType: str = ""
    emotionTags: list[str] = Field(default_factory=list)
    visualTags: list[str] = Field(default_factory=list)
    informationDensity: str = ""
    suggestedDurationSec: float = 0
    prefilledFields: list[str] = Field(default_factory=list)
    visionAnalysisStatus: str = "ready"
    message: str = ""


class MediaLibraryNodeRead(BaseModel):
    name: str
    relativePath: str
    nodeType: str
    mediaKind: str | None = None
    mediaType: str | None = None
    sizeBytes: int = 0
    hasAsset: bool = False
    children: list["MediaLibraryNodeRead"] = Field(default_factory=list)


class MediaLibraryScanRead(BaseModel):
    mediaRoot: str
    fileCount: int
    directoryCount: int
    truncated: bool = False
    tree: MediaLibraryNodeRead


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
    assetReuseEnabled: bool = False
    reusedAssetCount: int = 0
    reusedSegmentCount: int = 0
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
    audioFilePath: str = ""
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
    audioFilePath: str = ""
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


class CapcutDraftDeployRequest(BaseModel):
    jianyingDraftRoot: str = ""
    persistConfig: bool = True
    clearExisting: bool = False


class CapcutDraftDeployRead(BaseModel):
    projectId: str
    draftRoot: str
    draftFolderName: str
    draftFolderPath: str
    files: list[str]
    bgmIncluded: bool
    message: str


class CapcutExportDefaultsRead(BaseModel):
    defaultDraftRoot: str
    configuredDraftRoot: str
    effectiveDraftRoot: str


class ExportJsonImportRequest(BaseModel):
    content: str
    dryRun: bool = True
    conflictStrategy: str = "overwrite"
    fields: list[str] = Field(default_factory=lambda: ["subtitle"])


class ExportCsvImportRequest(BaseModel):
    content: str
    dryRun: bool = True
    conflictStrategy: str = "overwrite"
    fields: list[str] = Field(default_factory=lambda: ["subtitle"])
    columnMap: dict[str, str] = Field(default_factory=dict)


class ExportImportChangeRead(BaseModel):
    segmentId: str
    field: str
    currentValue: str
    incomingValue: str
    action: str


class ExportImportResultRead(BaseModel):
    schemaVersion: str
    dryRun: bool
    applied: bool
    fields: list[str]
    conflictStrategy: str
    changes: list[ExportImportChangeRead]
    updateCount: int
    skippedCount: int
    unchangedCount: int
    unknownSegmentIds: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


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
    subtitle: str = ""
    models: list["LlmModelOptionRead"] = Field(default_factory=list)


class LlmModelOptionRead(BaseModel):
    modelId: str
    label: str
    description: str = ""
    recommended: bool = False
    supportsVision: bool = False
    visionSource: str = "catalog"


class LlmVisionCapabilityRead(BaseModel):
    providerId: str
    providerName: str
    model: str
    supportsVision: bool
    visionSource: str = "catalog"
    message: str = ""
    configured: bool = False


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
    requiresPoll: bool = False


class LlmSubscriptionOAuthPollRead(BaseModel):
    status: str = "pending"
    message: str = ""
    configured: bool = False
    authType: str = ""


class LlmOAuthCallbackRequest(BaseModel):
    code: str
    state: str


class LlmOAuthRevokeRead(BaseModel):
    revoked: bool
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
