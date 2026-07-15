/** 剪映（CapCut）踩点语义，与后端 beat_grid.py 保持一致。 */

export const capcutBeatModeOptions = [
  { value: "none", label: "不启用节拍", description: "" },
  {
    value: "beat_1",
    label: "踩节拍1（粗密度）",
    description: "对齐剪映「踩节拍1」：优先使用粗粒度/强拍序列，适合慢歌或跟重拍切镜。"
  },
  {
    value: "beat_2",
    label: "踩节拍2（细密度）",
    description: "对齐剪映「踩节拍2」：使用全量细粒度起音序列，适合快切。"
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

export function applyBeatOffset(
  beatPoints: number[],
  targetDurationSec: number,
  offsetSec: number
) {
  if (!beatPoints.length) {
    return [];
  }
  if (Math.abs(offsetSec) < 0.001) {
    return normalizeBeatTimes(beatPoints, targetDurationSec);
  }

  const shifted = beatPoints
    .map((point) => Math.round((point + offsetSec) * 100) / 100)
    .filter((point) => point >= 0 && point <= targetDurationSec);
  return normalizeBeatTimes(shifted, targetDurationSec);
}

export function applyBeatCalibration(
  beatPoints: number[],
  targetDurationSec: number,
  offsetSec: number,
  scale = 1
) {
  if (!beatPoints.length) {
    return [];
  }
  if (Math.abs(offsetSec) < 0.001 && Math.abs(scale - 1) < 0.0001) {
    return normalizeBeatTimes(beatPoints, targetDurationSec);
  }

  const safeScale = Math.min(1.05, Math.max(0.95, scale));
  const transformed = beatPoints
    .map((point) => Math.round(((point * safeScale) + offsetSec) * 100) / 100)
    .filter((point) => point >= 0 && point <= targetDurationSec);
  return normalizeBeatTimes(transformed, targetDurationSec);
}

export function filterBeatsForCapcutMode(
  fineBeats: number[],
  beatMode: string,
  targetDurationSec: number,
  coarseBeats: number[] = []
) {
  if (beatMode === "none" || !fineBeats.length) {
    return [0, targetDurationSec];
  }

  const normalizedFine = normalizeBeatTimes(fineBeats, targetDurationSec);
  const normalizedCoarse = coarseBeats.length
    ? normalizeBeatTimes(coarseBeats, targetDurationSec)
    : normalizedFine;

  if (beatMode === "beat_2") {
    return normalizedFine;
  }

  if (beatMode === "beat_1") {
    if (coarseBeats.length >= 2) {
      return normalizedCoarse;
    }
    const filtered = normalizedFine.filter((_, index) => index % 2 === 0);
    return normalizeBeatTimes(filtered, targetDurationSec);
  }

  const source = coarseBeats.length ? normalizedCoarse : normalizedFine;
  if (coarseBeats.length) {
    const filtered = source.filter((_, index) => index % 2 === 0);
    return normalizeBeatTimes(filtered, targetDurationSec);
  }

  let filtered = source.filter((_, index) => index % 4 === 0);
  if (filtered.length < 2) {
    filtered = source.filter((_, index) => index % 2 === 0);
  }
  return normalizeBeatTimes(filtered, targetDurationSec);
}
