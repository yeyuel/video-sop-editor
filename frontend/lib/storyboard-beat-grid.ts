/**
 * 剪映踩点语义 — 与 backend/app/services/beat_grid.py 保持一致。
 */

const CAPCUT_BEAT_MODES = new Set(["none", "beat_1", "beat_2", "strong_weak"]);

export function normalizeBeatTimes(
  candidateTimes: number[],
  targetDurationSec: number,
  minGapSec = 0.08
): number[] {
  const uniquePoints: number[] = [];
  const sorted = [...new Set([0, ...candidateTimes, targetDurationSec])].sort(
    (left, right) => left - right
  );

  for (const rawTime of sorted) {
    const rounded = Number(rawTime.toFixed(2));
    if (rounded < 0 || rounded > targetDurationSec) {
      continue;
    }
    if (uniquePoints.length > 0 && rounded - uniquePoints[uniquePoints.length - 1] < minGapSec) {
      continue;
    }
    uniquePoints.push(rounded);
  }

  if (uniquePoints.length === 0) {
    return [0, targetDurationSec];
  }
  if (uniquePoints[0] !== 0) {
    uniquePoints.unshift(0);
  }
  if (uniquePoints[uniquePoints.length - 1] < targetDurationSec) {
    uniquePoints.push(Number(targetDurationSec.toFixed(2)));
  }
  return uniquePoints;
}

export function filterBeatsForCapcutMode(
  fineBeats: number[],
  beatMode: string,
  targetDurationSec: number,
  coarseBeats?: number[]
): number[] {
  if (beatMode === "none" || fineBeats.length === 0) {
    return [0, targetDurationSec];
  }

  const resolvedMode = CAPCUT_BEAT_MODES.has(beatMode) ? beatMode : "beat_1";
  const normalizedFine = normalizeBeatTimes(fineBeats, targetDurationSec);
  const normalizedCoarse =
    coarseBeats && coarseBeats.length > 0
      ? normalizeBeatTimes(coarseBeats, targetDurationSec)
      : normalizedFine;

  if (resolvedMode === "beat_2") {
    return normalizedFine;
  }

  if (resolvedMode === "beat_1") {
    if (coarseBeats && coarseBeats.length > 0 && normalizedCoarse.length >= 2) {
      return normalizedCoarse;
    }
    const filtered = normalizedFine.filter((_, index) => index % 2 === 0);
    return normalizeBeatTimes(filtered, targetDurationSec);
  }

  const source = coarseBeats && coarseBeats.length > 0 ? normalizedCoarse : normalizedFine;
  let filtered = source.filter((_, index) => index % 2 === 0);
  if (!(coarseBeats && coarseBeats.length > 0)) {
    filtered = source.filter((_, index) => index % 4 === 0);
    if (filtered.length < 2) {
      filtered = source.filter((_, index) => index % 2 === 0);
    }
  }
  return normalizeBeatTimes(filtered, targetDurationSec);
}
