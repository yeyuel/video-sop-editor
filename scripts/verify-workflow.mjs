#!/usr/bin/env node
/**
 * Sprint 3+ workflow 回归：验证 rhythm → storyboard 解锁逻辑（含 BGM analyzed 门禁）。
 * 运行：node scripts/verify-workflow.mjs
 */

function isRhythmAnalyzed(plan) {
  return (
    plan.bgmPhase === "analyzed" &&
    plan.analysisSource === "audio_upload" &&
    plan.beatPoints.length > 0 &&
    Boolean(plan.selectedBgmId) &&
    Boolean(plan.audioFileName)
  );
}

function getEnabledWorkflowSteps(workspace) {
  const enabled = ["create"];
  if (workspace.project.id) enabled.push("assets");
  if (workspace.assets.length > 0) enabled.push("theme");
  if (workspace.themes.length > 0 && workspace.project.selectedThemeId) {
    enabled.push("rhythm");
  }
  if (isRhythmAnalyzed(workspace.rhythmPlan)) enabled.push("storyboard");
  if (workspace.storyboard.length > 0) enabled.push("export");
  return enabled;
}

function getCompletedWorkflowSteps(workspace) {
  const completed = [];
  if (workspace.project.name) completed.push("create");
  if (workspace.assets.length > 0) completed.push("assets");
  if (workspace.project.selectedThemeId) completed.push("theme");
  if (isRhythmAnalyzed(workspace.rhythmPlan)) completed.push("rhythm");
  if (workspace.storyboard.length > 0) completed.push("storyboard");
  if (workspace.exportPlan.title && workspace.exportPlan.description) {
    completed.push("export");
  }
  return completed;
}

function assertEqual(actual, expected, label) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(`${label}\n  expected: ${e}\n  actual:   ${a}`);
  }
}

const emptyWorkspace = {
  project: { id: "p1", name: "demo", selectedThemeId: "" },
  assets: [],
  themes: [],
  rhythmPlan: { beatPoints: [], bgmPhase: "empty", analysisSource: "manual", selectedBgmId: "", audioFileName: "" },
  storyboard: [],
  exportPlan: { title: "", description: "" }
};

assertEqual(
  getEnabledWorkflowSteps(emptyWorkspace),
  ["create", "assets"],
  "有项目无素材时仅解锁录入"
);

const withAssets = {
  ...emptyWorkspace,
  assets: [{ assetId: "a1" }],
  themes: [{ id: "t1" }]
};
assertEqual(
  getEnabledWorkflowSteps(withAssets),
  ["create", "assets", "theme"],
  "有素材无选定主题时不解锁节奏"
);

const withTheme = {
  ...withAssets,
  project: { id: "p1", name: "demo", selectedThemeId: "t1" }
};
assertEqual(
  getEnabledWorkflowSteps(withTheme),
  ["create", "assets", "theme", "rhythm"],
  "选定主题后解锁节奏"
);

const withBeatPointsOnly = {
  ...withTheme,
  rhythmPlan: {
    beatPoints: [0, 1, 2],
    bgmPhase: "recommended",
    analysisSource: "manual",
    selectedBgmId: "bgm_1",
    audioFileName: ""
  }
};
assertEqual(
  getEnabledWorkflowSteps(withBeatPointsOnly),
  ["create", "assets", "theme", "rhythm"],
  "仅有节拍点但未完成 BGM 分析时不解锁分镜"
);

const withRhythm = {
  ...withTheme,
  rhythmPlan: {
    beatPoints: [0, 1, 2],
    bgmPhase: "analyzed",
    analysisSource: "audio_upload",
    selectedBgmId: "bgm_1",
    audioFileName: "track.mp3"
  }
};
assertEqual(
  getEnabledWorkflowSteps(withRhythm),
  ["create", "assets", "theme", "rhythm", "storyboard"],
  "BGM 已分析且有节拍点后解锁分镜"
);

const withStoryboard = {
  ...withRhythm,
  storyboard: [{ id: "s1" }]
};
assertEqual(
  getEnabledWorkflowSteps(withStoryboard),
  ["create", "assets", "theme", "rhythm", "storyboard", "export"],
  "有分镜后解锁导出"
);

assertEqual(
  getCompletedWorkflowSteps(withRhythm),
  ["create", "assets", "theme", "rhythm"],
  "完成态在分镜前停在节奏"
);

console.log("workflow regression: 7 checks passed");
