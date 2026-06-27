import { parseTimeSeconds } from "@/lib/time-input";

export const BEAT_ALIGN_TOLERANCE = 0.05;

export function roundTimeSeconds(value: number): number {
  return Number(value.toFixed(2));
}

export function formatTimeSeconds(value: number): string {
  return roundTimeSeconds(value).toString();
}

export function sortBeatPoints(beatPoints: number[]): number[] {
  return [...beatPoints].sort((left, right) => left - right);
}

export function isOnBeat(
  time: number,
  beatPoints: number[],
  tolerance = BEAT_ALIGN_TOLERANCE
): boolean {
  return beatPoints.some((point) => Math.abs(point - time) <= tolerance);
}

export function snapToNearestBeat(
  time: number,
  beatPoints: number[],
  options?: { min?: number; max?: number }
): number | null {
  if (beatPoints.length === 0) {
    return null;
  }

  const min = options?.min ?? Number.NEGATIVE_INFINITY;
  const max = options?.max ?? Number.POSITIVE_INFINITY;
  const candidates = beatPoints.filter((point) => point >= min && point <= max);
  if (candidates.length === 0) {
    return null;
  }

  let nearest = candidates[0];
  let bestDistance = Math.abs(time - nearest);

  for (const point of candidates) {
    const distance = Math.abs(time - point);
    if (distance < bestDistance - 1e-9) {
      bestDistance = distance;
      nearest = point;
    } else if (Math.abs(distance - bestDistance) <= 1e-9 && point > nearest) {
      nearest = point;
    }
  }

  return roundTimeSeconds(nearest);
}

export function snapTimeInputToBeat(
  value: string,
  beatPoints: number[],
  options?: { min?: number; max?: number; required?: boolean }
): string | null {
  const min = options?.min ?? 0;
  const max = options?.max ?? Number.POSITIVE_INFINITY;
  const parsed = parseTimeSeconds(value, { min: 0, max });
  if (parsed === null) {
    return options?.required === false ? null : null;
  }

  const clamped = Math.min(Math.max(parsed, min), max);
  const snapped = snapToNearestBeat(clamped, beatPoints, { min, max });
  if (snapped === null) {
    return null;
  }

  return formatTimeSeconds(snapped);
}

export function sliceBeatPointsInRange(
  beatPoints: number[],
  startTime: number,
  endTime: number
): number[] {
  const scoped = beatPoints
    .filter((point) => point >= startTime && point <= endTime)
    .map((point) => roundTimeSeconds(point));

  if (scoped.length > 0) {
    return scoped;
  }

  return [roundTimeSeconds(startTime), roundTimeSeconds(endTime)];
}

function beatsAfterStart(
  sortedBeats: number[],
  startBeat: number,
  targetDurationSec: number
): number[] {
  return sortedBeats.filter(
    (point) =>
      point > startBeat + BEAT_ALIGN_TOLERANCE &&
      point <= targetDurationSec + BEAT_ALIGN_TOLERANCE
  );
}

function findStartBeatForEnd(
  sortedBeats: number[],
  preferredStart: number,
  targetDurationSec: number
): number | null {
  let startBeat = snapToNearestBeat(preferredStart, sortedBeats, {
    min: 0,
    max: targetDurationSec
  });
  if (startBeat === null) {
    return null;
  }

  let startIndex = sortedBeats.findIndex(
    (point) => Math.abs(point - startBeat!) <= BEAT_ALIGN_TOLERANCE
  );
  if (startIndex === -1) {
    startIndex = sortedBeats.findIndex((point) => point >= startBeat!);
  }
  if (startIndex === -1) {
    return null;
  }

  for (let index = startIndex; index >= 0; index -= 1) {
    const candidateStart = sortedBeats[index];
    if (beatsAfterStart(sortedBeats, candidateStart, targetDurationSec).length > 0) {
      return candidateStart;
    }
  }

  return null;
}

function pickEndBeat(
  sortedBeats: number[],
  startBeat: number,
  preferredEnd: number,
  targetDurationSec: number
): number | null {
  const endCandidates = beatsAfterStart(sortedBeats, startBeat, targetDurationSec);
  if (endCandidates.length === 0) {
    return null;
  }

  const snappedEnd = snapToNearestBeat(preferredEnd, endCandidates, {
    max: targetDurationSec
  });
  if (snappedEnd !== null && snappedEnd > startBeat + BEAT_ALIGN_TOLERANCE) {
    return snappedEnd;
  }

  const lastCandidate = endCandidates[endCandidates.length - 1];
  if (lastCandidate > startBeat + BEAT_ALIGN_TOLERANCE) {
    return lastCandidate;
  }

  return null;
}

export function snapSegmentTimeRange(
  startText: string,
  endText: string,
  rhythmBeatPoints: number[],
  targetDurationSec: number
): {
  beatPointsText: string;
  endTimeText: string;
  startTimeText: string;
} | null {
  const sortedBeats = sortBeatPoints(rhythmBeatPoints);
  if (sortedBeats.length < 2) {
    return null;
  }

  const preferredStart = parseTimeSeconds(startText, { min: 0, max: targetDurationSec });
  const preferredEnd = parseTimeSeconds(endText, { min: 0, max: targetDurationSec });
  if (preferredStart === null || preferredEnd === null) {
    return null;
  }

  const startBeat = findStartBeatForEnd(sortedBeats, preferredStart, targetDurationSec);
  if (startBeat === null) {
    return null;
  }

  const endBeat = pickEndBeat(sortedBeats, startBeat, preferredEnd, targetDurationSec);
  if (endBeat === null) {
    return null;
  }

  const beatPoints = sliceBeatPointsInRange(sortedBeats, startBeat, endBeat);
  return {
    startTimeText: formatTimeSeconds(startBeat),
    endTimeText: formatTimeSeconds(endBeat),
    beatPointsText: beatPoints.join(", ")
  };
}

export function resolveSnappedSegmentTimes(
  startText: string,
  endText: string,
  rhythmBeatPoints: number[],
  targetDurationSec: number
): {
  beatPointsText: string;
  endTimeText: string;
  startTimeText: string;
} | null {
  const snapped = snapSegmentTimeRange(
    startText,
    endText,
    rhythmBeatPoints,
    targetDurationSec
  );
  if (snapped) {
    return snapped;
  }

  const startTime = parseTimeSeconds(startText, { min: 0, max: targetDurationSec });
  const endTime = parseTimeSeconds(endText, { min: 0, max: targetDurationSec });
  if (startTime === null || endTime === null || endTime <= startTime) {
    return null;
  }

  if (
    isOnBeat(startTime, rhythmBeatPoints) &&
    isOnBeat(endTime, rhythmBeatPoints)
  ) {
    return {
      startTimeText: formatTimeSeconds(startTime),
      endTimeText: formatTimeSeconds(endTime),
      beatPointsText: sliceBeatPointsInRange(rhythmBeatPoints, startTime, endTime).join(", ")
    };
  }

  return null;
}
