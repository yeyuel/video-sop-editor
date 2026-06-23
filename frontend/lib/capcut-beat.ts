/** 剪映（CapCut）踩点语义，与后端 beat_grid.py 保持一致。 */

export const capcutBeatModeOptions = [
  { value: "none", label: "不启用节拍", description: "" },
  {
    value: "beat_1",
    label: "踩节拍1（粗密度）",
    description: "对齐剪映「踩节拍1」：标记较稀疏，适合慢歌或只需跟重拍切镜。"
  },
  {
    value: "beat_2",
    label: "踩节拍2（细密度）",
    description: "对齐剪映「踩节拍2」：标记较稠密，捕捉更多细碎节奏点，适合快切。"
  },
  {
    value: "strong_weak",
    label: "强弱拍（强拍）",
    description: "对齐剪映「强弱拍」：只保留强拍/重拍位置，密度低于踩节拍1。"
  }
] as const;

export function getCapcutBeatModeLabel(value: string) {
  return capcutBeatModeOptions.find((option) => option.value === value)?.label ?? value;
}

export function getCapcutBeatModeDescription(value: string) {
  return capcutBeatModeOptions.find((option) => option.value === value)?.description ?? "";
}

function normalizeBeatTimes(candidateTimes: number[], targetDurationSec: number) {
  const uniquePoints: number[] = [];
  for (const rawTime of [...new Set([0, ...candidateTimes, targetDurationSec])].sort((a, b) => a - b)) {
    const rounded = Math.round(rawTime * 100) / 100;
    if (rounded < 0 || rounded > targetDurationSec) {
      continue;
    }
    if (uniquePoints.length && rounded - uniquePoints[uniquePoints.length - 1] < 0.08) {
      continue;
    }
    uniquePoints.push(rounded);
  }

  if (!uniquePoints.length) {
    return [0, targetDurationSec];
  }
  if (uniquePoints[0] !== 0) {
    uniquePoints.unshift(0);
  }
  if (uniquePoints[uniquePoints.length - 1] < targetDurationSec) {
    uniquePoints.push(targetDurationSec);
  }
  return uniquePoints;
}

export function filterBeatsForCapcutMode(
  allBeats: number[],
  beatMode: string,
  targetDurationSec: number
) {
  if (beatMode === "none" || !allBeats.length) {
    return [0, targetDurationSec];
  }

  const sortedBeats = normalizeBeatTimes(allBeats, targetDurationSec);
  if (beatMode === "beat_2") {
    return sortedBeats;
  }

  const stride = beatMode === "beat_1" ? 2 : 4;
  let filtered = sortedBeats.filter((_, index) => index % stride === 0);
  if (beatMode === "strong_weak" && filtered.length < 2) {
    filtered = sortedBeats.filter((_, index) => index % 2 === 0);
  }

  return normalizeBeatTimes(filtered, targetDurationSec);
}
